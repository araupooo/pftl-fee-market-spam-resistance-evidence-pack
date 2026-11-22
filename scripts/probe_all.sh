#!/bin/bash
# probe_all.sh — re-probe every live public endpoint used by this pack and
# retain the unedited responses under outputs/.
#
# Usage: bash scripts/probe_all.sh [OUTPUT_DIR]
#   OUTPUT_DIR defaults to outputs/ relative to the pack root.
# No credentials, sessions, or accounts are used. All endpoints are public.
# Each output file's full SHA-256 is printed to the probe log so a reader can
# verify that the shipped files are the files this script produced.
#
# SAFETY BOUNDARY (non-negotiable, see docs/methodology.md): BOUNDED
# OBSERVATION ONLY. This script performs read-only queries only. It sends no
# transactions, no flood traffic, and no load of any kind to the shared
# testnet. The heaviest call here is a single validated-ledger fetch with its
# transaction list, repeated 12 times at most, to count transactions per
# ledger. Total RPC calls: under 40.
set -u
PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$PACK_ROOT/outputs}"
mkdir -p "$OUT"
LOG="$OUT/probe-run.log"
: > "$LOG"
log() { echo "$*" | tee -a "$LOG"; }
sha() { sha256sum "$1" | awk '{print $1}'; }

log "probe_all.sh run start: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
log "pack root: $PACK_ROOT"
log "safety boundary: read-only queries only; no transactions, no flood traffic"

RPC="https://rpc.testnet.postfiat.org/"
post() { # $1 outfile $2 method-json
  curl -s -m 30 -X POST "$RPC" -H 'Content-Type: application/json' -d "$2" \
    -o "$OUT/$1" -w "%{http_code} %{time_total}s" > "$OUT/$1.http" 2>&1
  log "$1 -> $(cat "$OUT/$1.http") sha256=$(sha "$OUT/$1")"
  rm -f "$OUT/$1.http"
}
get() { # $1 url $2 outfile
  curl -s -m 30 "$1" -o "$OUT/$2" -w "%{http_code} %{time_total}s %{size_download}B" > "$OUT/$2.http" 2>&1
  log "$2 -> $(cat "$OUT/$2.http") sha256=$(sha "$OUT/$2")"
  rm -f "$OUT/$2.http"
}

# --- postfiatd JSON-RPC (public proxy) ---
post server_info.json '{"method":"server_info","params":[{}]}'
# The `ledger` method with ledger_index "validated" returns only the current
# index through this proxy; fetch the validated ledger by number instead so
# the full header (total_coins, close_time_resolution) is retained.
VALIDATED_SEQ="$(python3 -c "import json;print(json.load(open('$OUT/server_info.json'))['result']['info']['validated_ledger']['seq'])")"
log "validated seq for numeric ledger fetch: $VALIDATED_SEQ"
post ledger_current.json "{\"method\":\"ledger\",\"params\":[{\"ledger_index\":$VALIDATED_SEQ,\"transactions\":true,\"expand\":false}]}"
post ledger_closed.json '{"method":"ledger_closed","params":[{}]}'
post fee.json '{"method":"fee","params":[{}]}'
post feature_list.json '{"method":"feature","params":[{}]}'
post server_state.json '{"method":"server_state","params":[{}]}'
# Admin-gated methods: the public proxy is expected to refuse these; the
# refusal body itself is the evidence and is kept unedited.
post validators.json '{"method":"validators","params":[{}]}'
post peers.json '{"method":"peers","params":[{}]}'
post invalid_method.json '{"method":"no_such_method","params":[{}]}'

# --- Ledger-load sample: transaction counts of 12 consecutive validated
# ledgers (12 single read-only fetches). No transaction is submitted.
python3 - "$OUT" "$VALIDATED_SEQ" <<'PYEOF' 2>&1 | tee -a "$OUT/probe-run.log"
import json, subprocess, sys, hashlib
out, seq = sys.argv[1], int(sys.argv[2])
rows = []
for s in range(seq - 11, seq + 1):
    p = subprocess.run(
        ["curl", "-s", "-m", "30", "-X", "POST", "https://rpc.testnet.postfiat.org/",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"method": "ledger", "params": [{"ledger_index": s, "transactions": True, "expand": False}]})],
        capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
        txns = d["result"]["ledger"].get("transactions", [])
        rows.append({"seq": s, "txn_count": len(txns),
                     "close_time_human": d["result"]["ledger"].get("close_time_human")})
    except Exception as e:
        rows.append({"seq": s, "error": str(e), "raw": p.stdout[:200]})
with open(out + "/ledger-load-sample.json", "w") as f:
    json.dump(rows, f, indent=1)
print("ledger-load-sample.json sha256=%s" % hashlib.sha256(open(out + "/ledger-load-sample.json", "rb").read()).hexdigest())
print("ledger-load-sample: seqs %d-%d txn_counts %s" % (rows[0]["seq"], rows[-1]["seq"], [r.get("txn_count") for r in rows]))
PYEOF

# --- Response-header check: does the public RPC proxy advertise any
# per-client rate limit? (One HEAD-style fetch; headers only.)
curl -s -m 30 -D "$OUT/rpc-response-headers.txt" -o /dev/null -X POST "$RPC" \
  -H 'Content-Type: application/json' -d '{"method":"fee","params":[{}]}' || true
log "rpc-response-headers.txt sha256=$(sha "$OUT/rpc-response-headers.txt")"
grep -i "rate\|limit\|retry\|throttl" "$OUT/rpc-response-headers.txt" > "$OUT/rpc-rate-limit-headers.txt" || true
log "rpc-rate-limit-headers.txt sha256=$(sha "$OUT/rpc-rate-limit-headers.txt") (empty file = no rate-limit header observed)"

# --- Explorer ---
get https://explorer.testnet.postfiat.org/api/v1/metrics explorer_metrics.json
get https://explorer.testnet.postfiat.org/api/v1/health explorer_health.json

# --- Published pages ---
get https://postfiat.org/ postfiat_org.html
get https://postfiat.org/whitepaper/ postfiat_whitepaper.html
get https://docs.postfiat.org docs_postfiat_org.html
get https://postfiat.org/testnet_vl.json unl_testnet_vl.json

# --- Whitepaper plain text (derived, for keyword search; HTML is the source) ---
python3 - "$OUT/postfiat_whitepaper.html" "$OUT/whitepaper.txt" <<'PYEOF'
import re, html, sys
s = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
s = re.sub(r"<script.*?</script>", "", s, flags=re.S | re.I)
s = re.sub(r"<style.*?</style>", "", s, flags=re.S | re.I)
s = re.sub(r"<[^>]+>", " ", s)
s = html.unescape(s)
s = re.sub(r"\s+", " ", s)
open(sys.argv[2], "w").write(s)
print("whitepaper.txt chars=%d" % len(s))
PYEOF
log "whitepaper.txt sha256=$(sha "$OUT/whitepaper.txt")"
log "probe_all.sh run end: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
