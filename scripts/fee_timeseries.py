#!/usr/bin/env python3
"""fee_timeseries.py — bounded read-only fee-market time series.

Samples the public `fee` RPC plus the validated ledger sequence and the
transaction count of the validated ledger, once per --interval seconds,
--samples times. Each sample is 3 small read-only JSON-RPC calls; nothing is
submitted and no load is generated. Default: 20 samples x 30 s (~10 min).

Writes:
  outputs/fee-timeseries.jsonl — one JSON object per sample (unedited values)
  stdout — a summary log; the caller redirects it to outputs/fee-timeseries.log

Usage:
  python3 scripts/fee_timeseries.py --samples 20 --interval 30 \
      --out outputs/fee-timeseries.jsonl
"""
import argparse
import datetime
import hashlib
import json
import sys
import time
import urllib.request

RPC = "https://rpc.testnet.postfiat.org/"


def post(method, params):
    body = json.dumps({"method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    print("fee_timeseries.py start: %s samples=%d interval=%ds"
          % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             args.samples, args.interval))
    print("safety boundary: read-only queries only; no transactions, no flood traffic")
    rows = []
    for i in range(args.samples):
        t0 = datetime.datetime.now(datetime.timezone.utc)
        try:
            fee = post("fee", [{}])["result"]
            info = post("server_info", [{}])["result"]["info"]
            vseq = info["validated_ledger"]["seq"]
            ledger = post("ledger", [{"ledger_index": vseq, "transactions": True,
                                      "expand": False}])["result"]["ledger"]
            row = {
                "sample": i,
                "time_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "validated_seq": vseq,
                "txn_count_validated_ledger": len(ledger.get("transactions", [])),
                "base_fee_drops": fee["drops"]["base_fee"],
                "median_fee_drops": fee["drops"]["median_fee"],
                "minimum_fee_drops": fee["drops"]["minimum_fee"],
                "open_ledger_fee_drops": fee["drops"]["open_ledger_fee"],
                "median_level": fee["levels"]["median_level"],
                "minimum_level": fee["levels"]["minimum_level"],
                "open_ledger_level": fee["levels"]["open_ledger_level"],
                "reference_level": fee["levels"]["reference_level"],
                "current_ledger_size": fee["current_ledger_size"],
                "current_queue_size": fee["current_queue_size"],
                "expected_ledger_size": fee["expected_ledger_size"],
                "max_queue_size": fee["max_queue_size"],
                "load_factor_server_info": info.get("load_factor"),
                "peers": info.get("peers"),
            }
        except Exception as e:  # keep the failure visible, do not invent a row
            row = {"sample": i,
                   "time_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "error": repr(e)}
        rows.append(row)
        print("sample %d %s seq=%s base=%s median=%s open=%s queue=%s/%s txns=%s load=%s" % (
            i, row["time_utc"], row.get("validated_seq"), row.get("base_fee_drops"),
            row.get("median_fee_drops"), row.get("open_ledger_fee_drops"),
            row.get("current_queue_size"), row.get("max_queue_size"),
            row.get("txn_count_validated_ledger"), row.get("load_factor_server_info")))
        with open(args.out, "a") as f:
            f.write(json.dumps(row) + "\n")
        if i + 1 < args.samples:
            time.sleep(args.interval)

    ok = [r for r in rows if "error" not in r]
    print("fee_timeseries.py end: %d/%d samples ok" % (len(ok), len(rows)))
    if ok:
        for key in ("base_fee_drops", "median_fee_drops", "minimum_fee_drops",
                    "open_ledger_fee_drops", "current_queue_size",
                    "expected_ledger_size", "max_queue_size"):
            vals = {str(r[key]) for r in ok}
            print("  %s distinct values: %s" % (key, sorted(vals)))
        print("  txn_count_validated_ledger: min=%d max=%d mean=%.3f" % (
            min(r["txn_count_validated_ledger"] for r in ok),
            max(r["txn_count_validated_ledger"] for r in ok),
            sum(r["txn_count_validated_ledger"] for r in ok) / len(ok)))
        seqs = [r["validated_seq"] for r in ok]
        print("  validated_seq range: %d-%d (delta %d over %d samples)" % (
            min(seqs), max(seqs), max(seqs) - min(seqs), len(ok)))
    digest = hashlib.sha256(open(args.out, "rb").read()).hexdigest()
    print("fee-timeseries jsonl sha256=%s" % digest)
    return 0 if len(ok) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
