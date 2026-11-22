# Probe manifest

How every file in `outputs/` was produced. All probes are read-only
queries against public endpoints. No transactions were submitted, no flood
traffic was sent, no credentials or sessions were used.

## Single-shot probes (`scripts/probe_all.sh`)

Run start: 2026-11-22T18:47:58Z, run end: 2026-11-22T18:48:23Z.
Endpoint: `https://rpc.testnet.postfiat.org/` (postfiatd 1.0.9, network 2025).

| File | Method / URL | HTTP | Full SHA-256 (from probe-run.log) |
| --- | --- | --- | --- |
| `server_info.json` | `server_info` | 200 | d8bc7fead36d313696e61ab801308e5d87563eb97412d17ce61e325d285a4be4 |
| `ledger_current.json` | `ledger` (validated seq 8277391, transactions) | 200 | 0507fb919e86702a06a63733907067d27e76ff488403547536c21ef9c8c02251 |
| `ledger_closed.json` | `ledger_closed` | 200 | a99f6782084b6a100d87aa9bdfd6ef268b3f129670e1a6f7fb5100d20f943739 |
| `fee.json` | `fee` | 200 | 6c3d273f0c50e9d8f8088c728c908bdbefbda11766105a1cc74d55aef5b5072e |
| `feature_list.json` | `feature` | 200 | 70585f308ab55dfdc84093e95a21c3859099dcbf1c5b04f1f00cea3a6785984f |
| `server_state.json` | `server_state` | 200 | 4b3d5ca974b09a537f0473e3a3d0f6d5d9821a7ca81936dca5c7367ce3f7d182 |
| `validators.json` | `validators` | 403 | 91268711f43361e9d094089486492db986d6413020b6763903eb4c3b473216b4 |
| `peers.json` | `peers` | 403 | 91268711f43361e9d094089486492db986d6413020b6763903eb4c3b473216b4 |
| `invalid_method.json` | `no_such_method` | 200 | e7b21b8092a7192fb17ab985ff2ebd3de10df4b395311385249fdea2acd17540 |
| `ledger-load-sample.json` | 12 x `ledger` (seqs 8277380-8277391, transactions) | 200 | 779055de1dc8103de39b97e952e944c948979d8efd8262c65c8d9b9621a95034 |
| `rpc-response-headers.txt` | `fee` (headers only) | 200 | 40f02cabe2bb4d0ecfd11c2415b97f64024eedbc619748ed595febfbd24b562d |
| `rpc-rate-limit-headers.txt` | (filtered from the above; empty) | — | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| `explorer_metrics.json` | `https://explorer.testnet.postfiat.org/api/v1/metrics` | 200 | cafd29dba250425da17962b777c6efc6a2c10a27bb3058b44eeebffeb7991287 |
| `explorer_health.json` | `https://explorer.testnet.postfiat.org/api/v1/health` | 500 | de52b25e91c4558119b2a577b3d20a808e2bbca0f33b2caf63f5e81325a6a3ab |
| `postfiat_org.html` | `https://postfiat.org/` | 200 | 6242495541001392fab42bfbafd8251a43e8cbb97f4a2b4720f3664b131eaaeb |
| `postfiat_whitepaper.html` | `https://postfiat.org/whitepaper/` | 200 | 33b15b1a28f5ebdad68ccb3eeb719fc0e4738b8fe3e8ce89a5317143e7ba472c |
| `docs_postfiat_org.html` | `https://docs.postfiat.org` | 200 | 0ee1da936309b07922d14e33ae9414a6a0d3c4463aa306a0ae9d28692c30c4f2 |
| `unl_testnet_vl.json` | `https://postfiat.org/testnet_vl.json` | 200 | 5d4f5a18a18fead4105e5dc00cf7e11a71b9be4bc140357d1b4ea12116df59e7 |
| `whitepaper.txt` | Derived plain text from `postfiat_whitepaper.html` | — | 656238f6a11bfa179bdb27da68a6e9ad69a8ca9aa1f41c56b8b8d7b35c1b87a7 |

Notes:

- `validators.json` and `peers.json` have identical SHA-256 values because
  the proxy returns the same short refusal body (`Forbidden`) for both
  admin-gated methods.
- `ledger-load-sample.json` transaction counts: seqs 8277380-8277391 carried
  [0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0] transactions — 4 in total.
- `explorer_health.json` returned HTTP 500 with body
  `{"message":"rippled unreachable"}` while metrics returned HTTP 200.

## Fee time series (`scripts/fee_timeseries.py`)

20 samples, one every 30 seconds (~10 minutes), each sample 3 read-only
RPC calls (`fee`, `server_info`, `ledger` for the validated sequence).
See `outputs/fee-timeseries.log` for the per-sample lines and the summary,
and `outputs/derived/live-fee-market.json` for the derived statistics.

## Model (`src/fee_model.py`)

Pure computation, no network access. Inputs: `configs/fee-parameters.json`.
Outputs: `outputs/derived/escalation-model.json`,
`fixtures/escalation-model-table.csv`.

## Analysis (`scripts/analyze.py`)

Reads the probe outputs and the model, writes
`outputs/derived/live-fee-market.json`, `outputs/derived/ledger-load.json`,
`findings.json`, `run-manifest.json`, `docs/claim-index.md`,
`docs/gap-register.md`. No network access.

## Reproduction (`scripts/clean_reproduce.sh`)

Fresh-environment re-run: probes + 5-sample time series + model +
analysis + comparison. See `outputs/fresh-clone-compare.log` for the
per-check results.
