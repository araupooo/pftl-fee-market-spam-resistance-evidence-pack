# Methodology

## Safety boundary: bounded observation only

This pack was produced under a non-negotiable safety boundary, stated here
first because every other choice in the pack follows from it:

- **No transactions were submitted to the testnet.** Not one. No Payment,
  no AccountSet, no offer, no test transaction of any kind.
- **No flood traffic was sent.** No burst of requests, no load generation,
  no stress test against the shared testnet.
- **All probes are read-only queries** against public endpoints:
  `server_info`, `fee`, `ledger`, `ledger_closed`, `server_state`,
  `feature`, and the explorer's public metrics/health endpoints — plus two
  admin-gated methods (`validators`, `peers`) whose 403 refusal bodies are
  kept as evidence.
- **Total probe volume:** under 40 RPC calls in `scripts/probe_all.sh`
  (including 12 single-ledger reads to count transactions per ledger) and
  60 calls in the 20-sample fee time series (3 calls per sample). The
  network itself processes ~0.09 transactions per second; this pack's
  read traffic is a rounding error against it.
- **Load and stress findings come from pinned protocol parameters and
  modeling, never from flooding.** The escalation curve, the queue-fill
  costs, and the sustained-load scenarios in `src/fee_model.py` are pure
  computation from the pinned constants. The sustained-load simulation is a
  faithful re-implementation of the pinned `FeeMetrics::update` algorithm,
  run locally with no network contact at all.

Any claim in this pack that would need a transaction or a flood to test is
marked **UNTESTABLE** in `docs/claim-index.md` (C-24, C-25, C-26, C-28) and
is not asserted as measured. The honest statement of what could not be
tested is part of the evidence, not a gap in it.

## What was measured live

| Measurement | How | Where |
| --- | --- | --- |
| Base / median / minimum / open-ledger fee | `fee` RPC, single shot + 20 samples x 30 s | `outputs/fee.json`, `outputs/fee-timeseries.jsonl` |
| Queue size and capacity | `fee` RPC (`current_queue_size`, `max_queue_size`) | same |
| Expected ledger size | `fee` RPC (`expected_ledger_size`) | same |
| Load factors | `server_info` (`load_factor`) and `server_state` (all five `load_factor_*` fields) | `outputs/server_info.json`, `outputs/server_state.json` |
| Ledger cadence | Validated-sequence delta across the time series + explorer `ledger_interval` | `outputs/derived/live-fee-market.json` |
| Transactions per ledger | 12 consecutive validated ledgers fetched with `transactions: true`, plus the per-sample validated ledger in the time series | `outputs/ledger-load-sample.json`, `outputs/fee-timeseries.jsonl` |
| Reserves and supply | Validated-ledger header (`reserve_base`, `reserve_inc`, `total_coins`) | `outputs/ledger_current.json` |
| Network load (independent source) | Explorer metrics endpoint | `outputs/explorer_metrics.json` |
| Admin gating | `validators` and `peers` RPCs | `outputs/validators.json`, `outputs/peers.json` (both 403) |
| Proxy rate-limit advertisement | Response headers of a `fee` call | `outputs/rpc-response-headers.txt`, `outputs/rpc-rate-limit-headers.txt` (empty) |

## What was pinned, not measured

The protocol revision is pinned to commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10, PR #50 merge,
tag v1.0.9), verified as the local clone's HEAD and matching the live
`build_version: 1.0.9`. Every cited line number was checked with `grep -n`
against that clone. Blob SHA-1 values for every cited file are in
`fixtures/source-hashes.json`; verbatim excerpts with line numbers are in
`fixtures/source-excerpts/`.

The testnet configuration (`cfg/postfiatd-testnet-full.cfg` at the pinned
revision) leaves the `[transaction_queue]` section entirely commented out
(lines 531-669 contain zero non-comment lines) and the `[voting]` section
likewise, so every queue parameter and the 10-drop reference fee are the
code defaults. The excerpt is preserved in
`configs/postfiatd-testnet-full-transaction-queue-excerpt.txt`.

## What was modeled

`src/fee_model.py` computes, from the pinned constants only:

1. The open-ledger escalation curve (fee for the next reference transaction
   as a function of transactions already in the open ledger).
2. The cumulative minimum cost of filling the open ledger with 33-512
   reference transactions.
3. Queue capacity, queue-fill fee cost, accounts needed to fill the queue,
   and the reserve locked by that fill.
4. Server-local load-fee bounds (LoadFeeTrack).
5. Per-endpoint resource-charge thresholds (how many requests of each cost
   class reach the warn/drop thresholds inside one decay window).
6. A faithful simulation of `FeeMetrics::update` under four ledger-size
   scenarios (idle, 100 tx/ledger flood, 1000 tx/ledger flood, flood with a
   slow-consensus ledger).

The model assumes an attacker pays the escalated minimum at every position.
That is a worst-case willingness-to-pay assumption; the sustained-load note
in the model output explains where it breaks (the required fee exceeds the
entire PFT supply within a few ledgers, so real transactions queue instead
and the multiplier stops compounding).

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
check passes. The fresh probe set is kept under `outputs/fresh-clone-*` and
is verified by the comparison log, not by SHA256SUMS (which is made before
the reproduce run).

## Limitations

- The testnet was idle during the whole probe window (0-4 transactions per
  ledger across all samples). Every statement about behaviour under load is therefore a
  code-or-model statement, not a measurement. The four UNTESTABLE claims
  say so explicitly.
- The public RPC proxy is a black box: its rate-limit policy, if any, is
  not advertised and cannot be confirmed without abusive traffic. The
  resource-charge analysis applies to the node's peer layer, where the
  code is pinned; whether the proxy enforces the same charges is unknown.
- Only one node (the public RPC endpoint, hostid MUFF) was observed. Fee
  state is per-node for the load factor and per-network for the queue and
  escalation; the observed values are the reporting node's view.
- The explorer health endpoint returned HTTP 500 during the probe window
  while metrics returned HTTP 200; both responses are kept unedited.
