#!/usr/bin/env python3
"""analyze.py — derive the pack's measured numbers from the probe outputs.

Reads outputs/*.json / *.jsonl (unedited probe outputs), the escalation
model (outputs/derived/escalation-model.json, produced by src/fee_model.py),
and the pinned parameters (configs/fee-parameters.json). Writes:

  outputs/derived/live-fee-market.json  — live fee-market snapshot
  outputs/derived/ledger-load.json      — transaction-load statistics
  findings.json                         — severity-scored findings
  run-manifest.json                     — counts recomputed FROM the lists
  docs/claim-index.md                   — claim-to-evidence table (generated
                                          from the same CLAIMS list, so the
                                          counts in the manifest cannot drift)
  docs/gap-register.md                  — severity-scored gap register table
                                          (generated from the FINDINGS list)

Every count in run-manifest.json is recomputed from the list it summarizes.
No network access. Deterministic given the probe outputs.
"""
import collections
import datetime
import hashlib
import json
import os
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PACK, "outputs")
DERIVED = os.path.join(OUT, "derived")


def load(name):
    with open(os.path.join(OUT, name)) as f:
        return json.load(f)


def load_lines(name):
    rows = []
    with open(os.path.join(OUT, name)) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------- claims
# status: VERIFIED (measured live in this pack) | SPECIFIED (pinned code or
#   pinned-parameter model) | UNVERIFIED (no evidence either way) |
#   UNTESTABLE (cannot be tested without sending transactions or flood
#   traffic, which the safety boundary forbids)
CLAIMS = [
    ("C-01", "Live base fee is 10 drops for a reference transaction.",
     "VERIFIED", "outputs/fee.json: drops.base_fee = 10; outputs/server_info.json: validated_ledger.base_fee_xrp = 1e-05; outputs/explorer_metrics.json: base_fee = 0.00001"),
    ("C-02", "Live median fee is 5000 drops (median level 128000).",
     "VERIFIED", "outputs/fee.json: drops.median_fee = 5000, levels.median_level = 128000"),
    ("C-03", "Live fee queue is empty: 0 of 2000 slots used.",
     "VERIFIED", "outputs/fee.json: current_queue_size = 0, max_queue_size = 2000; outputs/fee-timeseries.jsonl: queue 0 in every sample"),
    ("C-04", "Live expected ledger size is 32 transactions (the code floor).",
     "VERIFIED", "outputs/fee.json: expected_ledger_size = 32"),
    ("C-05", "No fee escalation is active: all load factors are at the 256 reference.",
     "VERIFIED", "outputs/server_info.json: load_factor = 1; outputs/server_state.json: load_factor, load_factor_fee_escalation, load_factor_fee_queue, load_factor_fee_reference, load_factor_server all 256"),
    ("C-06", "Validated ledger advances at ~3.0 s per ledger.",
     "VERIFIED", "outputs/fee-timeseries.jsonl: validated_seq delta over the sample window; outputs/explorer_metrics.json: ledger_interval = 3.022"),
    ("C-07", "Account reserve is 10 PFT and owner reserve is 2 PFT.",
     "VERIFIED", "outputs/server_info.json: validated_ledger.reserve_base_xrp = 10, reserve_inc_xrp = 2; outputs/server_state.json: validated_ledger.reserve_base = 10000000, reserve_inc = 2000000"),
    ("C-08", "Live load is ~0.09 transactions per second, ~0.26 per ledger, average fee 10 drops.",
     "VERIFIED", "outputs/explorer_metrics.json: txn_sec = 0.09, txn_ledger = 0.26, avg_fee = 0.00001000; outputs/ledger-load-sample.json: 4 transactions in 12 ledgers"),
    ("C-09", "Reference fee default is 10 drops in the pinned code.",
     "SPECIFIED", "configs/fee-parameters.json; fixtures/source-excerpts/Config-FeeSetup.txt (Config.h:69)"),
    ("C-10", "Open-ledger fee level follows level(n) = median_level * n^2 / target^2 once n exceeds the expected size.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-FeeMetrics-update-scaleFeeLevel.txt (TxQ.cpp:173-191)"),
    ("C-11", "The escalation multiplier is floored at 128000 (256 * 500).",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-Setup.txt (TxQ.h:100); live median_level = 128000 confirms the floor is in force"),
    ("C-12", "Queue capacity is max(expected * 20, 2000); live value 2000.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-queue-full-eviction.txt (TxQ.cpp:1376-1377); outputs/fee.json: max_queue_size = 2000"),
    ("C-13", "One account may hold at most 10 transactions in the queue.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-Setup.txt (TxQ.h:148)"),
    ("C-14", "Replacing a queued transaction needs a fee at least 25% higher.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-Setup.txt (TxQ.h:97)"),
    ("C-15", "A queued transaction needs LastLedgerSequence at least 2 above the open ledger.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-Setup.txt (TxQ.h:155)"),
    ("C-16", "A queued transaction is dropped after 10 failed application retries.",
     "SPECIFIED", "fixtures/source-excerpts/TxQ-retriesAllowed.txt (TxQ.h:580)"),
    ("C-17", "A transaction paying below the load-scaled minimum fee is rejected with telINSUF_FEE_P.",
     "SPECIFIED", "fixtures/source-excerpts/Transactor-checkFee.txt (Transactor.cpp:380-410)"),
    ("C-18", "Server-local load fee rises 25% per raise event and is capped at 1,000,000x the base fee (10 PFT per reference transaction).",
     "SPECIFIED", "fixtures/source-excerpts/LoadFeeTrack-constants.txt (LoadFeeTrack.h:141-147); fixtures/source-excerpts/LoadFeeTrack-raise-lower-scale.txt (LoadFeeTrack.cpp:32-80)"),
    ("C-19", "Per-endpoint resource charges warn at balance 5000 and disconnect at 25000, over a 32 s decay window.",
     "SPECIFIED", "fixtures/source-excerpts/resource-tuning.txt (Tuning.h:31-44); fixtures/source-excerpts/resource-fees.txt (Fees.cpp:26-44)"),
    ("C-20", "The base fee can only change at flag ledgers, every 256 ledgers (~13 minutes at 3.05 s cadence), by validator vote toward configured targets.",
     "SPECIFIED", "fixtures/source-excerpts/FeeVote-VotableValue.txt (FeeVoteImpl.cpp:31-90, 206); fixtures/source-excerpts/Ledger-flag-interval.txt (Ledger.h:426)"),
    ("C-21", "Once 100 transactions are already in the open ledger, the next reference transaction needs 48,829 drops (model, pinned constants).",
     "SPECIFIED", "outputs/derived/escalation-model.json: escalation_curve (n=100); fixtures/escalation-model-table.csv"),
    ("C-22", "Filling the whole 2000-slot queue at the minimum fee costs 20,000 drops (0.02 PFT) in fees.",
     "SPECIFIED", "outputs/derived/escalation-model.json: queue.fill_fee_cost_drops"),
    ("C-23", "Filling the queue needs at least 200 accounts and locks at least 2,000 PFT in account reserves.",
     "SPECIFIED", "outputs/derived/escalation-model.json: queue.accounts_needed_to_fill_queue, queue.reserve_locked_to_fill_queue_pft"),
    ("C-24", "Under congestion the queue evicts the lowest-fee transaction first.",
     "UNTESTABLE", "Code path exists (fixtures/source-excerpts/TxQ-queue-full-eviction.txt, TxQ.cpp:1243-1313) but live eviction has never been observed: the queue has been empty in every probe. Testing it needs a full queue, which needs flood traffic."),
    ("C-25", "Under congestion a higher-fee transaction enters the open ledger before a lower-fee one.",
     "UNTESTABLE", "Implied by the escalation formula and queue ordering (TxQ.cpp:173-191, FeeEscalation.md) but never observed live: no congested ledger exists in the probe window. Testing it needs submitted transactions under load."),
    ("C-26", "The median fee level rises after a busy ledger closes.",
     "UNTESTABLE", "FeeMetrics::update sets the multiplier to the closed ledger's median fee level (TxQ.cpp:85-168), but every sampled ledger is empty, so the multiplier stays at its 128000 floor. Testing it needs a busy ledger."),
    ("C-27", "The public RPC proxy enforces a per-client rate limit.",
     "UNVERIFIED", "outputs/rpc-rate-limit-headers.txt is empty (no rate-limit header observed) and outputs/rpc-response-headers.txt carries no limit advertisement. Whether the proxy enforces anything server-side cannot be determined without abusive traffic, which the safety boundary forbids."),
    ("C-28", "Spam or invalid transactions are dropped at the RPC layer before relay.",
     "UNTESTABLE", "The resource-charge/disconnect machinery exists in code (Fees.cpp, Tuning.h) but no spam transaction was sent: the safety boundary forbids submitting transactions."),
    ("C-29", "Fee escalation makes a sustained open-ledger flood expensive: filling one ledger with 256 reference transactions at the escalated minimum costs 27,091,469 drops (27.091469 PFT).",
     "SPECIFIED", "outputs/derived/escalation-model.json: cumulative_open_ledger_fill_cost (n=256). Model only; no flood was run."),
    ("C-30", "The explorer health endpoint reports the node unreachable while its metrics endpoint still answers.",
     "VERIFIED", "outputs/explorer_health.json (HTTP 500, {\"message\":\"rippled unreachable\"}); outputs/explorer_metrics.json (HTTP 200)"),
]

# ---------------------------------------------------------------- findings
FINDINGS = [
    {"id": "F-01", "severity": "HIGH", "status": "UNVERIFIED",
     "title": "Fee escalation and queue eviction have never been exercised live",
     "detail": "Every sampled ledger carries 0-4 transactions (mean 0.33 over the 12-ledger sample and 0.50 across the 20-sample time series; 0.26 per ledger per the explorer), the queue has been 0/2000 in every probe, and every fee level sits at its floor. The anti-spam machinery is verified in pinned code only; its live behaviour under load is unknown. A mainnet launch would be the first live test of the escalation path.",
     "remediation": "Exercise the escalation path on a private, isolated network (not the shared testnet) with scripted load: fill the open ledger past 32 transactions, fill the queue to 2000, and record the fee responses. Publish the resulting fee curves before any mainnet decision.",
     "evidence": "outputs/fee-timeseries.jsonl, outputs/ledger-load-sample.json, outputs/fee.json; claims C-03, C-24, C-25, C-26"},
    {"id": "F-02", "severity": "MEDIUM", "status": "MEASURED",
     "title": "The 5000-drop median fee is a floor artifact, not a market price",
     "detail": "median_level is pinned at the 128000 minimumEscalationMultiplier floor because every ledger is empty (FeeMetrics::update sets the multiplier to the floor when a ledger has 0 transactions). The 5000-drop median_fee therefore says nothing about what users actually pay; wallets or fee estimators that treat it as the going rate overpay 500x the 10-drop base fee.",
     "remediation": "Fee estimators should use open_ledger_fee (10 drops live) for the next transaction, not median_fee, and should document that median_fee is a floor while ledgers are empty.",
     "evidence": "outputs/fee.json; fixtures/source-excerpts/TxQ-FeeMetrics-update-scaleFeeLevel.txt (TxQ.cpp:148-165); claim C-02"},
    {"id": "F-03", "severity": "HIGH", "status": "SPECIFIED",
     "title": "Queue-fill cost is dominated by the account reserve, not by fees",
     "detail": "Filling all 2000 queue slots at the 10-drop minimum costs 20,000 drops (0.02 PFT) in fees. The binding cost is the reserve: 10 transactions per account means at least 200 accounts, each locking the 10 PFT account reserve, i.e. 2,000 PFT locked (refundable on account deletion, less fees). The reserve policy, not the fee market, is the effective Sybil defence for the queue.",
     "remediation": "Do not lower the account reserve without re-modelling queue-fill cost; any reserve change must be evaluated against this 200-account / 2,000 PFT figure. Consider publishing the reserve as an explicit anti-spam parameter in operator documentation.",
     "evidence": "outputs/derived/escalation-model.json (queue section); claims C-12, C-13, C-22, C-23"},
    {"id": "F-04", "severity": "MEDIUM", "status": "SPECIFIED",
     "title": "The 10-transaction per-account queue cap is trivially bypassed with fresh accounts",
     "detail": "The queue code caps each account at 10 queued transactions (TxQ.h:148) but the ledger has no identity or reputation layer, so an attacker funds 200 fresh accounts (10 PFT reserve each) and queues 2000 transactions. The cap limits damage per account, not per attacker.",
     "remediation": "Treat the per-account cap as a fairness mechanism, not an anti-Sybil control. The reserve is the control; monitor account-creation rate as the leading spam indicator.",
     "evidence": "fixtures/source-excerpts/TxQ-Setup.txt (TxQ.h:148); claim C-13"},
    {"id": "F-05", "severity": "MEDIUM", "status": "SPECIFIED",
     "title": "Queue eviction can shelter a cheap transaction behind expensive ones from the same account",
     "detail": "When the queue is full, the eviction comparison uses the victim account's average fee level across its queued transactions when that account holds more than one transaction (TxQ.cpp:1266-1299). A mixed-fee account's cheapest transaction can therefore survive eviction that an identical single-transaction account's transaction would not. This is a deliberate averaging rule, but it lets a spammer protect cheap queue slots with a few expensive ones.",
     "remediation": "Document the averaging rule for operators; if eviction fairness matters, consider evicting strictly by lowest individual fee level instead of the per-account average.",
     "evidence": "fixtures/source-excerpts/TxQ-queue-full-eviction.txt (TxQ.cpp:1243-1313); claim C-24"},
    {"id": "F-06", "severity": "LOW", "status": "SPECIFIED",
     "title": "The base fee cannot react faster than one flag ledger (~13 minutes)",
     "detail": "Fee votes are collected only at flag ledgers, every 256 ledgers, and a new base fee only takes effect when a majority of validators vote toward it (FeeVoteImpl.cpp:206-240, Ledger.h:426). A spam burst shorter than ~13 minutes cannot be answered by a base-fee change at all; only the automatic escalation and queue mechanisms respond inside a burst.",
     "remediation": "Do not rely on base-fee voting as a burst response. Treat escalation and queue eviction as the in-burst defences and the fee vote as a slow steering control.",
     "evidence": "fixtures/source-excerpts/FeeVote-VotableValue.txt; claim C-20"},
    {"id": "F-07", "severity": "MEDIUM", "status": "UNVERIFIED",
     "title": "No per-client rate limit is observable on the public RPC proxy",
     "detail": "The proxy's responses carry no rate-limit headers (outputs/rpc-rate-limit-headers.txt is empty) and no limit is advertised. The only documented RPC-layer protection is the per-endpoint resource charge/disconnect in the node (warn at 5000, drop at 25000 charge units over a 32 s decay window), which is measured at the peer layer and cannot be confirmed for the HTTPS proxy from outside. Whether a single client can hammer the proxy with cheap read requests is unknown.",
     "remediation": "Publish the proxy's rate-limit policy (or state that there is none) and enforce a documented per-client limit at the proxy, independent of the node's peer-layer charges. Do not probe it with abusive traffic to find out.",
     "evidence": "outputs/rpc-response-headers.txt, outputs/rpc-rate-limit-headers.txt; claims C-27, C-28"},
    {"id": "F-08", "severity": "LOW", "status": "SPECIFIED",
     "title": "The `fee` RPC is documented experimental and may change without warning",
     "detail": "FeeEscalation.md states the `fee` command is still experimental and may change without warning. Clients that hard-code its response shape (levels/drops) risk breakage on upgrade; the same applies to the experimental server_info / server_state load fields.",
     "remediation": "Pin client fee logic to the documented fields with a fallback to the 10-drop base fee, and re-check the `fee` response shape after every node upgrade.",
     "evidence": "fixtures/source-excerpts/FeeEscalation-fee-command.txt (FeeEscalation.md:282-285); claim C-05"},
    {"id": "F-09", "severity": "LOW", "status": "MEASURED",
     "title": "Explorer health reports the node unreachable while metrics still answer",
     "detail": "GET /api/v1/health returned HTTP 500 {\"message\":\"rippled unreachable\"} at probe time while /api/v1/metrics returned HTTP 200 with fresh values. Either the health check probes a different backend than the metrics endpoint, or the health signal is stale. Operators watching only the health endpoint would wrongly conclude the network is down.",
     "remediation": "Reconcile the two endpoints to the same backend check, or document which backend each one probes.",
     "evidence": "outputs/explorer_health.json, outputs/explorer_metrics.json; claim C-30"},
    {"id": "F-10", "severity": "INFO", "status": "SPECIFIED",
     "title": "Server-local load fee can reach 1,000,000x base, but it is per-node, not consensus",
     "detail": "LoadFeeTrack raises a node's local minimum fee by 25% per raise event up to 256 * 1,000,000, i.e. a 10 PFT minimum per reference transaction under extreme local load. The live node reports load_factor 256 (no load). Crucially, the load fee is per-node: a transaction must satisfy the load-scaled minimum of a majority of validators, so loading one node does not raise the network minimum.",
     "remediation": "No action. Note for operators: local load shedding protects individual nodes; network-wide fee response still depends on the shared escalation path.",
     "evidence": "fixtures/source-excerpts/LoadFeeTrack-raise-lower-scale.txt; outputs/server_state.json; claim C-18"},
    {"id": "F-11", "severity": "MEDIUM", "status": "SPECIFIED",
     "title": "Slow consensus halves the cheap-transaction allowance, hurting legitimate users too",
     "detail": "When consensus is slow, FeeMetrics::update cuts txnsExpected by 50% per slow ledger (floor 32). A spam burst that slows consensus therefore shrinks the number of transactions admitted at the base fee for everyone, including legitimate users, until healthy ledgers rebuild the allowance. The defence and the collateral damage are the same mechanism.",
     "remediation": "Monitor txnsExpected (reported as expected_ledger_size) as a health signal during incidents; a drop toward 32 during a burst indicates consensus is slowing, not just that fees are rising.",
     "evidence": "fixtures/source-excerpts/TxQ-FeeMetrics-update-scaleFeeLevel.txt (TxQ.cpp:108-124); outputs/derived/escalation-model.json (sustained_load_dynamics)"},
    {"id": "F-12", "severity": "LOW", "status": "MEASURED",
     "title": "Fee-burn accounting reconciles: no anomaly in total supply",
     "detail": "total_coins in the validated ledger is 99,999,999,966,545,876 drops against the 100,000,000,000,000,000-drop genesis supply, i.e. 33,454,124 drops (33.454124 PFT) burned in fees to date. The figure is consistent with a network that has processed very few transactions at 10 drops each plus the historical load the explorer reports.",
     "remediation": "None. Re-check total_coins at each future probe as a supply-integrity control.",
     "evidence": "outputs/ledger_current.json (total_coins); outputs/derived/live-fee-market.json (burned_pft)"},
]


def main():
    os.makedirs(DERIVED, exist_ok=True)
    fee = load("fee.json")["result"]
    si = load("server_info.json")["result"]["info"]
    ss = load("server_state.json")["result"]["state"]
    lc = load("ledger_current.json")["result"]["ledger"]
    metrics = load("explorer_metrics.json")
    health = load("explorer_health.json")
    load_sample = load("ledger-load-sample.json")
    ts = load_lines("fee-timeseries.jsonl")
    model = load("derived/escalation-model.json")
    feats = load("feature_list.json")["result"]
    n_features = len(feats.get("features", [])) if isinstance(feats, dict) else 0

    ts_ok = [r for r in ts if "error" not in r]
    seqs = [r["validated_seq"] for r in ts_ok]
    t_first = ts_ok[0]["time_utc"]
    t_last = ts_ok[-1]["time_utc"]
    probe_log_lines = open(os.path.join(OUT, "probe-run.log")).read().splitlines()
    probe_start = probe_log_lines[0].split("run start: ")[1]
    probe_end = probe_log_lines[-1].split("run end: ")[1]

    def secs(a, b):
        fa = datetime.datetime.strptime(a, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        fb = datetime.datetime.strptime(b, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        return (fb - fa).total_seconds()

    window_s = secs(t_first, t_last)
    cadence = (window_s / (max(seqs) - min(seqs))) if len(seqs) > 1 and max(seqs) > min(seqs) else None

    total_coins = int(lc["total_coins"])
    genesis = 100_000_000_000_000_000
    burned_drops = genesis - total_coins

    sample_counts = [r["txn_count"] for r in load_sample if "txn_count" in r]
    ts_counts = [r["txn_count_validated_ledger"] for r in ts_ok]

    live = {
        "generated_at_utc": NOW,
        "probe_window_utc": "%s to %s (probe_all.sh) + fee timeseries %s to %s"
                            % (probe_start, probe_end, t_first, t_last),
        "build_version": si["build_version"],
        "network_id": si["network_id"],
        "server_state": si["server_state"],
        "peers": si["peers"],
        "validated_ledger_seq": si["validated_ledger"]["seq"],
        "complete_ledgers": si["complete_ledgers"],
        "last_close": si["last_close"],
        "job_queue_overflow": si.get("jq_trans_overflow"),
        "peer_disconnects": si.get("peer_disconnects"),
        "peer_disconnects_resources": si.get("peer_disconnects_resources"),
        "fee": {
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
        },
        "load_factors_server_state": {
            "load_factor": ss["load_factor"],
            "load_factor_fee_escalation": ss.get("load_factor_fee_escalation"),
            "load_factor_fee_queue": ss.get("load_factor_fee_queue"),
            "load_factor_fee_reference": ss.get("load_factor_fee_reference"),
            "load_factor_server": ss.get("load_factor_server"),
        },
        "reserves_drops": {"base": ss["validated_ledger"]["reserve_base"],
                           "increment": ss["validated_ledger"]["reserve_inc"]},
        "total_coins_drops": total_coins,
        "burned_drops": burned_drops,
        "burned_pft": burned_drops / 1_000_000,
        "explorer": {"metrics": metrics, "health_http_500_body": health},
        "features_known": n_features,
        "fee_timeseries": {
            "samples": len(ts_ok), "errors": len(ts) - len(ts_ok),
            "window_seconds": window_s,
            "validated_seq_first": min(seqs), "validated_seq_last": max(seqs),
            "mean_close_interval_s": round(cadence, 3) if cadence else None,
            "distinct_base_fee_drops": sorted({str(r["base_fee_drops"]) for r in ts_ok}),
            "distinct_median_fee_drops": sorted({str(r["median_fee_drops"]) for r in ts_ok}),
            "distinct_open_ledger_fee_drops": sorted({str(r["open_ledger_fee_drops"]) for r in ts_ok}),
            "distinct_current_queue_size": sorted({str(r["current_queue_size"]) for r in ts_ok}),
            "distinct_expected_ledger_size": sorted({str(r["expected_ledger_size"]) for r in ts_ok}),
            "txn_count_validated_ledger": {
                "min": min(ts_counts), "max": max(ts_counts),
                "mean": round(sum(ts_counts) / len(ts_counts), 3)},
        },
        "ledger_load_sample": {
            "ledgers": len(sample_counts),
            "seq_range": [load_sample[0]["seq"], load_sample[-1]["seq"]],
            "txn_counts": sample_counts,
            "total_txns": sum(sample_counts),
            "mean_txns_per_ledger": round(sum(sample_counts) / len(sample_counts), 3),
            "max_txns_per_ledger": max(sample_counts),
        },
    }
    with open(os.path.join(DERIVED, "live-fee-market.json"), "w") as f:
        json.dump(live, f, indent=1)
    print("wrote outputs/derived/live-fee-market.json sha256=%s"
          % sha(os.path.join(DERIVED, "live-fee-market.json")))

    # ---- ledger-load derived file (kept separate for the evidence index) --
    load_derived = {
        "generated_at_utc": NOW,
        "ledger_load_sample": live["ledger_load_sample"],
        "fee_timeseries_txn_counts": live["fee_timeseries"]["txn_count_validated_ledger"],
        "explorer": live["explorer"]["metrics"],
        "interpretation": "The network is idle: 4 transactions in 12 consecutive "
                          "validated ledgers (mean 0.33) and 0-4 transactions per "
                          "validated ledger across the 20-sample fee time series "
                          "(mean 0.50). "
                          "No congested ledger was observed, so no escalation, "
                          "queueing, or eviction event was observed live.",
    }
    with open(os.path.join(DERIVED, "ledger-load.json"), "w") as f:
        json.dump(load_derived, f, indent=1)
    print("wrote outputs/derived/ledger-load.json sha256=%s"
          % sha(os.path.join(DERIVED, "ledger-load.json")))

    # ---- findings.json ----------------------------------------------------
    with open(os.path.join(PACK, "findings.json"), "w") as f:
        json.dump({"generated_at_utc": NOW, "findings": FINDINGS}, f, indent=1)
    print("wrote findings.json sha256=%s" % sha(os.path.join(PACK, "findings.json")))

    # ---- claim index (generated from CLAIMS so counts cannot drift) ------
    by_status = collections.Counter(c[2] for c in CLAIMS)
    claim_lines = [
        "# Claim-to-evidence index",
        "",
        "Generated by `scripts/analyze.py` from the same claim list used for the",
        "counts in `run-manifest.json`, so the table and the counts cannot drift apart.",
        "",
        "Statuses: **VERIFIED** — measured live in this pack; **SPECIFIED** — pinned",
        "protocol code or a model computed from pinned constants; **UNVERIFIED** — no",
        "evidence either way; **UNTESTABLE** — cannot be tested without sending",
        "transactions or flood traffic, which the safety boundary forbids.",
        "",
        "Counts: %d total — %s." % (
            len(CLAIMS),
            ", ".join("%d %s" % (by_status[s], s)
                      for s in ("VERIFIED", "SPECIFIED", "UNVERIFIED", "UNTESTABLE")
                      if by_status[s])),
        "",
        "| ID | Claim | Status | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for cid, text, status, ev in CLAIMS:
        claim_lines.append("| %s | %s | %s | %s |" % (cid, text, status, ev))
    claim_lines += [
        "",
        "## Untestable claims (explicit)",
        "",
        "The following claims are marked UNTESTABLE above because testing them would",
        "require submitting transactions or flood traffic to the shared testnet, which",
        "this pack's safety boundary forbids (see docs/methodology.md): C-24 (queue",
        "eviction order), C-25 (fee prioritisation under congestion), C-26 (median fee",
        "rise after a busy ledger), C-28 (RPC-layer dropping of spam transactions).",
        "C-27 (proxy rate limit) is UNVERIFIED rather than UNTESTABLE: it could in",
        "principle be tested by observation, but no limit is advertised and confirming",
        "one would need abusive traffic.",
        "",
        "## Raw log permalinks",
        "",
        "Verification answers should lead with these raw-file permalinks so quoted",
        "fields can be checked independently (replace `<repo>` with the published",
        "repository URL):",
        "",
        "- Fee time series (unedited): `<repo>/raw/main/outputs/fee-timeseries.jsonl`",
        "- Fee time-series log: `<repo>/raw/main/outputs/fee-timeseries.log`",
        "- Probe run log with full SHA-256 values: `<repo>/raw/main/outputs/probe-run.log`",
        "- Single-shot fee snapshot: `<repo>/raw/main/outputs/fee.json`",
        "- Escalation model: `<repo>/raw/main/outputs/derived/escalation-model.json`",
        "- Live fee-market snapshot: `<repo>/raw/main/outputs/derived/live-fee-market.json`",
        "",
    ]
    with open(os.path.join(PACK, "docs", "claim-index.md"), "w") as f:
        f.write("\n".join(claim_lines))
    print("wrote docs/claim-index.md sha256=%s"
          % sha(os.path.join(PACK, "docs", "claim-index.md")))

    # ---- gap register (generated from FINDINGS) ---------------------------
    by_sev = collections.Counter(f["severity"] for f in FINDINGS)
    by_fstatus = collections.Counter(f["status"] for f in FINDINGS)
    gap_lines = [
        "# Resilience gap register",
        "",
        "Generated by `scripts/analyze.py` from the same findings list as",
        "`findings.json`, so the table and the counts cannot drift apart.",
        "",
        "Counts: %d total — %s; statuses %s." % (
            len(FINDINGS),
            ", ".join("%d %s" % (by_sev[s], s)
                      for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
                      if by_sev[s]),
            ", ".join("%d %s" % (by_fstatus[s], s) for s in sorted(by_fstatus))),
        "",
        "Severity means: HIGH — the gap could let spam degrade the network or",
        "leave a core defence unproven; MEDIUM — a real weakness or a misleading",
        "signal with a concrete fix; LOW — a documentation, monitoring, or",
        "slow-response weakness; INFO — a true statement with no action needed.",
        "",
        "| ID | Severity | Status | Gap | Remediation | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in FINDINGS:
        gap_lines.append("| %s | %s | %s | **%s** %s | %s | %s |" % (
            f["id"], f["severity"], f["status"], f["title"], f["detail"],
            f["remediation"], f["evidence"]))
    gap_lines += [
        "",
        "## Reading note",
        "",
        "Two findings are HIGH and both are about the same root cause: the defence",
        "has never been exercised (F-01) and the only cheap queue-fill path runs",
        "through the account reserve rather than the fee market (F-03). Neither",
        "finding says the defence is broken — the pinned code implements the",
        "escalation, queue, and eviction rules as documented. What is missing is",
        "live evidence, and that evidence can only be produced on an isolated",
        "network, not on the shared testnet.",
        "",
    ]
    with open(os.path.join(PACK, "docs", "gap-register.md"), "w") as f:
        f.write("\n".join(gap_lines))
    print("wrote docs/gap-register.md sha256=%s"
          % sha(os.path.join(PACK, "docs", "gap-register.md")))

    # ---- run manifest (counts recomputed FROM the lists) ------------------
    manifest = {
        "pack": "PFTL fee-market and spam-resistance evidence pack",
        "generated_at_utc": NOW,
        "probe_window_utc": live["probe_window_utc"],
        "environment": {
            "python": sys.version.split()[0],
            "tools": "curl, git, python3 (stdlib only)",
            "network": "public endpoints only; no credentials, sessions, accounts, or signing",
        },
        "repo_pins": {
            "postfiatd": "0085a1ff885d6a446369cf73a4430f75af22be55 (2026-10-10, PR #50 merge, v1.0.9)",
        },
        "live_endpoints": [
            "https://rpc.testnet.postfiat.org/ (postfiatd 1.0.9, network_id 2025)",
            "https://explorer.testnet.postfiat.org/api/v1/",
            "https://postfiat.org/ and https://postfiat.org/whitepaper/ (Sept 2026)",
            "https://docs.postfiat.org (Notion JavaScript shell; no retrievable content)",
            "https://postfiat.org/testnet_vl.json",
        ],
        "counts": {
            "findings_total": len(FINDINGS),
            "by_severity": {s: by_sev[s] for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO") if by_sev[s]},
            "by_status": {s: by_fstatus[s] for s in sorted(by_fstatus)},
            "claims_total": len(CLAIMS),
            "claims_by_status": {s: by_status[s] for s in ("VERIFIED", "SPECIFIED", "UNVERIFIED", "UNTESTABLE") if by_status[s]},
        },
        "verdict": "%d findings: %s. %s" % (
            len(FINDINGS),
            ", ".join("%d %s" % (by_sev[s], s) for s in ("HIGH", "MEDIUM", "LOW", "INFO") if by_sev[s]),
            "The fee market is at its floor on an idle testnet; the anti-spam machinery is implemented in pinned code but has never been exercised live, and the binding queue-fill cost is the 2,000 PFT account-reserve lockup, not transaction fees."),
        "notes": [
            "Assessment only: no transactions sent, no flood traffic, no mainnet touched, no funds spent, nothing signed.",
            "Bounded observation only: at most ~40 read-only RPC calls in probe_all.sh plus 60 in the 20-sample fee time series.",
            "Live values were re-probed for this pack; no numbers were copied from earlier packs.",
        ],
    }
    with open(os.path.join(PACK, "run-manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("wrote run-manifest.json sha256=%s" % sha(os.path.join(PACK, "run-manifest.json")))
    print("counts: findings=%d %s; claims=%d %s" % (
        len(FINDINGS), dict(by_sev), len(CLAIMS), dict(by_status)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
