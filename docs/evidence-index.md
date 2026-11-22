# Evidence index

Every file in this pack, what it is, and which claim or finding it supports.
Probe outputs are unedited responses; derived files are produced by the
scripts named in each row. Full SHA-256 values are in `SHA256SUMS` (except
the `fresh-clone-*` files, which are verified by
`outputs/fresh-clone-compare.log`).

## Probe outputs (`outputs/`)

| File | Contents | Supports |
| --- | --- | --- |
| `probe-run.log` | Probe run log with full SHA-256 of every output file | All live claims |
| `fee.json` | Single-shot `fee` RPC response | C-01, C-02, C-03, C-04, C-05 |
| `fee-timeseries.jsonl` | 20 samples x 30 s of `fee` + validated ledger + tx counts | C-01-C-06, C-08 |
| `fee-timeseries.log` | Time-series run log with per-sample lines and full SHA-256 | C-01-C-06, C-08 |
| `server_info.json` | `server_info` response (build, network, peers, load, validated ledger) | C-05, C-06, C-07 |
| `server_state.json` | `server_state` response (all five load factors, reserves) | C-05, C-07 |
| `ledger_current.json` | Validated ledger header with transactions (0 txs) and total_coins | F-12, C-08 |
| `ledger_closed.json` | `ledger_closed` response | C-06 |
| `ledger-load-sample.json` | Transaction counts of 12 consecutive validated ledgers | C-08, F-01 |
| `feature_list.json` | 101 known amendments | Context |
| `validators.json`, `peers.json` | 403 refusal bodies (admin-gated methods) | Methodology (admin gating) |
| `invalid_method.json` | Error body for an unknown method | Methodology (proxy behaviour) |
| `explorer_metrics.json` | Explorer load figures | C-06, C-08 |
| `explorer_health.json` | HTTP 500 "rippled unreachable" | C-30, F-09 |
| `rpc-response-headers.txt` | Response headers of a `fee` call | C-27, F-07 |
| `rpc-rate-limit-headers.txt` | Empty: no rate-limit header observed | C-27, F-07 |
| `postfiat_org.html`, `postfiat_whitepaper.html`, `whitepaper.txt`, `docs_postfiat_org.html`, `unl_testnet_vl.json` | Published pages and validator list, unedited | Context |
| `derived/live-fee-market.json` | Live snapshot derived by `scripts/analyze.py` | C-01-C-08, F-02, F-12 |
| `derived/ledger-load.json` | Load statistics derived by `scripts/analyze.py` | C-08, F-01 |
| `derived/escalation-model.json` | Model computed by `src/fee_model.py` | C-21, C-22, C-23, C-29, F-03, F-11 |
| `fresh-clone-*` | Fresh-environment reproduction probe set | Reproduction (see below) |
| `fresh-clone-compare.log` | Comparison log: every check PASS/FAIL + overall line | Reproduction |
| `fresh-clone-analyze.log`, `fresh-clone-model.log` | Fresh-run logs | Reproduction |

## Model and analysis (`src/`, `scripts/`)

| File | Contents | Supports |
| --- | --- | --- |
| `src/fee_model.py` | Escalation curve, fill costs, queue model, load-fee bounds, resource charges, sustained-load simulation | C-21, C-22, C-23, C-29, F-03, F-05, F-11 |
| `scripts/probe_all.sh` | All live probes (read-only) | All live claims |
| `scripts/fee_timeseries.py` | Fee time series sampler (read-only) | C-01-C-06, C-08 |
| `scripts/analyze.py` | Derives live snapshot, findings, manifest, claim index, gap register | All counts |
| `scripts/compare_reproduce.py` | Fresh-vs-shipped comparison with per-check PASS/FAIL | Reproduction |
| `scripts/clean_reproduce.sh` | Full fresh-environment reproduction | Reproduction |
| `scripts/extract_excerpts.py` | Verbatim pinned-source excerpts + blob hashes | All SPECIFIED claims |
| `scripts/verify_digests.sh`, `scripts/make_sha256sums.sh` | Digest verification / generation | Integrity |

## Parameters, fixtures, docs

| File | Contents | Supports |
| --- | --- | --- |
| `configs/fee-parameters.json` | Every pinned constant with its file:line source | All SPECIFIED claims |
| `configs/pinned-revision.txt` | Pinned commit, date, tag, verification method | Provenance |
| `configs/postfiatd-testnet-full-transaction-queue-excerpt.txt` | Verbatim cfg lines 531-669 (all commented) | C-09-C-16 (defaults apply) |
| `fixtures/source-excerpts/*.txt` | 21 verbatim code excerpts with commit + line ranges | All SPECIFIED claims |
| `fixtures/source-hashes.json` | Git blob SHA-1 of every cited file at the pinned commit | Provenance |
| `fixtures/escalation-model-table.csv` | Escalation curve as CSV | C-21 |
| `findings.json` | 12 severity-scored findings | Gap register |
| `run-manifest.json` | Pack manifest; counts recomputed from the lists | Counts |
| `docs/methodology.md` | Safety boundary, methods, limitations | Method |
| `docs/escalation-model.md` | Model derivation and tables | C-21-C-23, C-29 |
| `docs/decision-memo.md` | Launch-readiness assessment | Verdict |
| `docs/claim-index.md` | 30 claims with statuses and evidence (generated) | All claims |
| `docs/gap-register.md` | 12 findings with remediations (generated) | All findings |
| `docs/citations.md` | Every source with file:line or URL | Provenance |
| `docs/index.html` | Results page (summarises findings, links evidence) | Results page |
| `README.md` | Pack overview and reproduction instructions | Entry point |
| `SHA256SUMS` | Full SHA-256 of every shipped file except `fresh-clone-*` | Integrity |

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
