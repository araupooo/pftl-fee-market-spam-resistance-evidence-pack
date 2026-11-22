# Citations

Pinned revision for every code citation: postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10, PR #50 merge,
tag v1.0.9), repository https://github.com/postfiatorg/postfiatd. Line
numbers were verified with `grep -n` against the local clone at that
commit. Blob SHA-1 values: `fixtures/source-hashes.json`. Verbatim excerpts:
`fixtures/source-excerpts/`.

## Pinned protocol sources

| # | Source | What it establishes |
| --- | --- | --- |
| S-01 | `src/xrpld/app/misc/TxQ.h:60-160` (excerpt `TxQ-Setup.txt`) | Queue setup defaults: 20 ledgers in queue, 2000 minimum queue size, 25% replacement increase, 128000 minimum escalation multiplier, 32 minimum txs in ledger, 256 target txs, 20% growth, 50% slow cut, 10 txs per account, 2 last-ledger buffer |
| S-02 | `src/xrpld/app/misc/TxQ.h:375-420` (excerpt `TxQ-FeeMetrics-ctor.txt`) | FeeMetrics starts at txnsExpected 32, target 256, multiplier 128000 |
| S-03 | `src/xrpld/app/misc/TxQ.h:575-585` (excerpt `TxQ-retriesAllowed.txt`) | Queued transactions are dropped after 10 failed retries |
| S-04 | `src/xrpld/app/misc/detail/TxQ.cpp:85-195` (excerpt `TxQ-FeeMetrics-update-scaleFeeLevel.txt`) | FeeMetrics::update (growth, slow cut, median multiplier) and scaleFeeLevel (quadratic escalation formula) |
| S-05 | `src/xrpld/app/misc/detail/TxQ.cpp:1240-1330` (excerpt `TxQ-queue-full-eviction.txt`) | Queue-full eviction: lowest fee dropped, per-account average-fee comparison |
| S-06 | `src/xrpld/app/misc/detail/TxQ.cpp:1777-1800` (excerpt `TxQ-getMetrics.txt`) | getMetrics: minimum processing fee is the base level while the queue is not full, lowest queued level + 1 when full |
| S-07 | `src/xrpld/app/misc/detail/TxQ.cpp:1860-1913` (excerpt `TxQ-doRPC.txt`) | doRPC: how the `fee` RPC response is built from the metrics |
| S-08 | `src/xrpld/app/misc/detail/TxQ.cpp:1914-1982` (excerpt `TxQ-setup_TxQ.txt`) | setup_TxQ: configuration keys for the queue section |
| S-09 | `src/xrpld/app/misc/LoadFeeTrack.h:139-150` (excerpt `LoadFeeTrack-constants.txt`) | LoadFeeTrack constants: normal factor 256, +/- 1/4, cap 256 x 1,000,000 |
| S-10 | `src/xrpld/app/misc/detail/LoadFeeTrack.cpp:28-112` (excerpt `LoadFeeTrack-raise-lower-scale.txt`) | raise/lower local fee and scaleFeeLoad |
| S-11 | `src/xrpld/app/misc/FeeEscalation.md:1-90, 90-155, 224-323` (excerpts `FeeEscalation-*.txt`) | Design document: escalation, queue, constants, `fee` command (experimental), server_info/server_state fee fields |
| S-12 | `src/libxrpl/resource/Fees.cpp:20-49` (excerpt `resource-fees.txt`) | Per-request resource charges (reference RPC 20, medium 400, heavy 3000, invalid signature 2000, warning 4000, drop 6000) |
| S-13 | `include/xrpl/resource/detail/Tuning.h:24-50` (excerpt `resource-tuning.txt`) | Resource tuning: warn 5000, drop 25000, decay window 32 s, gossip minimum 1000 |
| S-14 | `src/xrpld/core/Config.h:60-80` (excerpt `Config-FeeSetup.txt`) | FeeSetup defaults: reference fee 10 drops, account reserve 10 PFT, owner reserve 2 PFT |
| S-15 | `src/xrpld/app/tx/detail/Transactor.cpp:370-445` (excerpt `Transactor-checkFee.txt`) | checkFee: below-minimum fee rejected with telINSUF_FEE_P |
| S-16 | `src/xrpld/app/misc/FeeVoteImpl.cpp:25-92` (excerpt `FeeVote-VotableValue.txt`) | VotableValue: votes counted only between current and target; majority wins |
| S-17 | `src/xrpld/app/ledger/Ledger.h:420-430` (excerpt `Ledger-flag-interval.txt`) | FLAG_LEDGER_INTERVAL = 256 |
| S-18 | `src/xrpld/app/misc/NetworkOPs.cpp:2985-2996` (excerpt `NetworkOPs-server-info-load-fields.txt`) | server_info fields: jq_trans_overflow, peer_disconnects, peer_disconnects_resources |
| S-19 | `cfg/postfiatd-testnet-full.cfg:531-669` (excerpt in `configs/`) | The [transaction_queue] section is entirely commented out: code defaults apply |
| S-20 | `cfg/postfiatd-testnet-full.cfg:1215-1249` (commented [voting] section) | reference_fee / account_reserve / owner_reserve unset: code defaults apply |

## Live sources (re-probed for this pack, 2026-11-22 18:47-19:00 UTC)

| # | Source | What it establishes |
| --- | --- | --- |
| L-01 | `https://rpc.testnet.postfiat.org/` (`server_info`, `fee`, `ledger`, `ledger_closed`, `server_state`, `feature`) | Build 1.0.9, network 2025, 21 peers, validated ledger, fee levels, queue state, reserves, supply |
| L-02 | `https://explorer.testnet.postfiat.org/api/v1/metrics` | Independent load figures: 0.09 txn/s, 0.26 txn/ledger, 3.022 s interval, avg fee 10 drops |
| L-03 | `https://explorer.testnet.postfiat.org/api/v1/health` | HTTP 500 "rippled unreachable" at probe time |
| L-04 | `https://postfiat.org/`, `https://postfiat.org/whitepaper/` | Published pages (no fee-market parameters stated there; whitepaper kept for keyword search) |
| L-05 | `https://postfiat.org/testnet_vl.json` | Testnet validator list (kept unedited; not used for fee claims) |

## Notes on the design document

FeeEscalation.md contains one stale figure: its "Other Constants" section
says the minimum `lastLedgerMedianFeeLevel` value is 500, while the code
(TxQ.h:100) and the live median_level both say 128000 (256 x 500). The
code and the live value agree; the document's 500 is the pre-multiplication
factor, not the level. This pack cites the code value.

The `fee` command section of the same document states the command "is
still experimental, and may change without warning" — cited as finding F-08.
