# PFTL Fee-Market and Spam-Resistance Evidence Pack

A public assessment of the PFTL fee market and spam resistance, built from
live testnet observations and the pinned protocol source code. Assessment
only: no transactions were sent, no flood traffic was generated, no mainnet
was touched, nothing was signed, no funds were spent.

## Verdict

**Not yet proven — sound on paper, untested in practice.** The pinned code
implements a coherent, layered defence (fee escalation, transaction queue
with eviction, per-account queue caps, server-local load fees, per-endpoint
resource charges, validator-voted base fee), and every parameter is at its
documented default on the testnet. But the testnet is idle, so no part of
the defence has ever been observed working under load. See
`docs/decision-memo.md` for the full assessment.

## Headline measured numbers (live testnet, network 2025, 2026-11-22 18:47-19:00 UTC)

| Measurement | Value |
| --- | --- |
| Build / network / state | postfiatd 1.0.9, network_id 2025, `full`, 21 peers |
| Validated ledger | seq 8,277,391 at probe start; 8,277,406-8,277,611 across the time series |
| Ledger cadence | mean close interval 3.024 s (explorer: 3.022 s) |
| Base fee | 10 drops (constant across all 20 time-series samples) |
| Median fee | 5000 drops — a code-floor artifact, not a market price (see F-02) |
| Open-ledger fee | 10 drops (constant) |
| Fee queue | 0 / 2000 in every sample |
| Expected ledger size | 32 transactions (the code floor) |
| Load factors | All 256 (no escalation, no load) |
| Transactions per ledger | 4 in 12 consecutive ledgers (mean 0.33); 0-4 across the time series (mean 0.50) |
| Explorer load | 0.09 txn/s, 0.26 txn/ledger, avg fee 10 drops |
| Reserves | 10 PFT account reserve, 2 PFT owner reserve |
| Fees burned to date | 33.454124 PFT |
| Job-queue overflow / resource disconnects | 0 / 0 |

## Headline modelled numbers (pinned constants, no traffic sent)

| Quantity | Value |
| --- | --- |
| Fee for the next tx once 32 are in the open ledger | 10 drops |
| Fee for the next tx once 33 are in the open ledger | 5,318 drops |
| Fee for the next tx once 100 are in the open ledger | 48,829 drops |
| Fee for the next tx once 256 are in the open ledger | 320,000 drops |
| Cost to fill one ledger with 256 reference txs | 27.091469 PFT |
| Cost to fill the 2,000-slot queue (fees only) | 20,000 drops (0.02 PFT) |
| Accounts / reserve locked to fill the queue | 200 accounts / 2,000 PFT |
| Server-local load-fee cap | 1,000,000x base (10 PFT per reference tx) |

## Counts (recomputed from the lists they summarise)

- Findings: **12 total — 2 HIGH, 5 MEDIUM, 4 LOW, 1 INFO; statuses 3 MEASURED, 7 SPECIFIED, 2 UNVERIFIED**
- Claims: **30 total — 9 VERIFIED, 16 SPECIFIED, 1 UNVERIFIED, 4 UNTESTABLE**

The four UNTESTABLE claims (C-24, C-25, C-26, C-28) would need submitted
transactions or flood traffic to test, which this pack's safety boundary
forbids. They are marked explicitly in `docs/claim-index.md`, not asserted.

## Safety boundary

**Bounded observation only.** No transactions were submitted to the
testnet. No flood traffic was sent. All probes are read-only queries
against public endpoints (under 40 RPC calls in `probe_all.sh`, 60 in the
time series). Load and stress findings come from pinned protocol
parameters and modeling, never from flooding. The boundary is documented
in `docs/methodology.md` and in the header of every probe script.

## Contents

- `docs/index.html` — results page: findings summary with links to evidence
- `docs/methodology.md` — safety boundary, methods, limitations
- `docs/escalation-model.md` — fee-escalation curve, queue-fill costs, sustained-load simulation
- `docs/decision-memo.md` — launch-readiness assessment
- `docs/claim-index.md` — 30 claims with statuses and evidence (generated)
- `docs/gap-register.md` — 12 severity-scored findings with remediations (generated)
- `docs/citations.md` — every source with file:line or URL
- `docs/evidence-index.md` — every file and what it supports
- `src/fee_model.py` — the escalation/spam-cost model (pure computation)
- `scripts/probe_all.sh`, `scripts/fee_timeseries.py` — the live probes (read-only)
- `scripts/analyze.py` — derives the live snapshot, findings, manifest
- `scripts/clean_reproduce.sh` — fresh-environment reproduction (exit 0)
- `configs/fee-parameters.json` — every pinned constant with its file:line source
- `fixtures/source-excerpts/` — 21 verbatim code excerpts with line numbers
- `fixtures/source-hashes.json` — git blob SHA-1 of every cited file
- `outputs/` — unedited probe outputs, time series, derived files, fresh-clone set
- `findings.json`, `run-manifest.json`, `SHA256SUMS`

## Pinned revision

postfiatd commit `0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10,
PR #50 merge, tag v1.0.9). Every cited line number was verified with
`grep -n` against a local clone at that commit. See
`configs/pinned-revision.txt`.

## Reproduction

```bash
bash scripts/probe_all.sh        # re-probe every live endpoint (read-only)
python3 scripts/fee_timeseries.py --samples 20 --interval 30 \
    --out outputs/fee-timeseries.jsonl   # 10-minute fee time series
python3 src/fee_model.py         # recompute the model (no network)
python3 scripts/analyze.py       # regenerate derived files, findings, manifest
bash scripts/clean_reproduce.sh  # full fresh-environment check, exit 0
bash scripts/verify_digests.sh   # verify SHA256SUMS
```

`clean_reproduce.sh` copies the pack to a throwaway directory, drops all
shipped probe outputs, re-runs the probes with a short (5-sample) time
series, recomputes the model and the analysis, and compares the fresh
derived numbers with the shipped ones. It exits 0 only if every comparison
check passes. The fresh probe set is kept under `outputs/fresh-clone-*`.

## Raw log permalinks

Verification answers should lead with these raw-file permalinks so quoted
fields can be checked independently (replace `<repo>` with the published
repository URL):

- `<repo>/raw/main/outputs/fee-timeseries.jsonl`
- `<repo>/raw/main/outputs/fee-timeseries.log`
- `<repo>/raw/main/outputs/probe-run.log`
- `<repo>/raw/main/outputs/fee.json`
- `<repo>/raw/main/outputs/derived/escalation-model.json`
- `<repo>/raw/main/outputs/derived/live-fee-market.json`
