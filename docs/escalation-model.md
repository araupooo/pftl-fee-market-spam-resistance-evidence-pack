# Fee-escalation and spam-cost model

All numbers in this document are computed by `src/fee_model.py` from the
pinned constants in `configs/fee-parameters.json`. Nothing here was
measured by sending traffic. The full computed tables are in
`outputs/derived/escalation-model.json` and
`fixtures/escalation-model-table.csv`.

## Pinned inputs (live values, re-probed for this pack)

| Parameter | Value | Source |
| --- | --- | --- |
| Reference fee (base fee) | 10 drops | `fee.json`; Config.h:69 |
| Base fee level | 256 | TxQ.h:64 |
| Expected ledger size (`txnsExpected`) | 32 (the code floor) | `fee.json`; TxQ.h:103 |
| Median fee level (escalation multiplier) | 128000 (the code floor, 256 x 500) | `fee.json`; TxQ.h:100 |
| Queue capacity | 2000 = max(32 x 20, 2000) | `fee.json`; TxQ.cpp:1376-1377 |
| Maximum transactions per account in queue | 10 | TxQ.h:148 |
| Account reserve | 10,000,000 drops (10 PFT) | `server_state.json`; Config.h:72 |
| Replacement fee increase | 25% | TxQ.h:97 |

## 1. Open-ledger escalation curve

The pinned formula (`TxQ::FeeMetrics::scaleFeeLevel`, TxQ.cpp:173-191) is:

```
level(n) = 256                                  if n <= 32
level(n) = 128000 * n^2 / 32^2                  if n > 32
drops(n) = ceil(level(n) * 10 / 256)            for a reference transaction
```

where `n` is the number of transactions already in the open ledger and
`drops(n)` is the minimum fee for the next reference transaction. The
rounding-up follows the node's `doRPC` behaviour (TxQ.cpp:1900-1909).

| Transactions already in open ledger | Fee level for next tx | Fee (drops) for next reference tx |
| --- | --- | --- |
| 0-32 | 256 | 10 |
| 33 | 136,125 | 5,318 |
| 35 | 153,125 | 5,982 |
| 40 | 200,000 | 7,813 |
| 50 | 312,500 | 12,208 |
| 64 | 512,000 | 20,000 |
| 80 | 800,000 | 31,250 |
| 100 | 1,250,000 | 48,829 |
| 128 | 2,048,000 | 80,000 |
| 200 | 5,000,000 | 195,313 |
| 256 | 8,192,000 | 320,000 |
| 512 | 32,768,000 | 1,280,000 |
| 1000 | 125,000,000 | 4,882,813 |

Reading: the first 32 transactions in a ledger cost 10 drops each. The
33rd already costs 5,318 drops — a 532x jump for one extra transaction.
That cliff is the whole point of the design: the 33rd transaction is where
escalation starts, and it starts hard.

Cross-check against the pinned design document: FeeEscalation.md works an
example with limit 6 and the 128000 floor, and states the 8th transaction
needs a level of about 174,000. The same formula gives
128000 * 7^2 / 6^2 = 174,222. The document's example and this model agree.

## 2. Cumulative cost of filling the open ledger

Each transaction paying exactly the escalated minimum at its position:

| Transactions in ledger | Total minimum fees (drops) | Total (PFT) |
| --- | --- | --- |
| 33 | 330 | 0.000330 |
| 40 | 44,767 | 0.044767 |
| 50 | 141,868 | 0.141868 |
| 64 | 361,207 | 0.361207 |
| 100 | 1,547,779 | 1.547779 |
| 256 | 27,091,469 | 27.091469 |
| 512 | 217,758,485 | 217.758485 |

A single-ledger flood of 256 reference transactions costs at least 27.09
PFT in fees at the escalated minimum — and that is only the first ledger.
See section 5 for what happens when the flood continues.

## 3. Queue-fill cost

| Quantity | Value |
| --- | --- |
| Queue capacity | 2,000 transactions |
| Fee cost to fill at the 10-drop minimum | 20,000 drops (0.02 PFT) |
| Accounts needed (10 txs each) | 200 |
| Account reserve locked by those accounts | 2,000,000,000 drops (2,000 PFT) |

The fee cost of filling the queue is negligible (0.02 PFT). The binding
cost is the reserve: 2,000 PFT locked across 200 accounts. The reserve is
refundable on account deletion (less fees), so even that is a lockup, not
a burn — but it is a 100,000x larger number than the fee cost, and it is
the only thing standing between a spammer and a full queue. Any proposal
to lower the account reserve must re-run this arithmetic first.

## 4. Server-local load fee (per-node)

`LoadFeeTrack` (LoadFeeTrack.h:141-147, LoadFeeTrack.cpp:32-80) raises a
node's local minimum fee by 25% per raise event, from a factor of 256 up
to 256 * 1,000,000 — a 1,000,000x multiplier, i.e. a 10 PFT minimum per
reference transaction (10,000,000 drops). It takes 62 raises to go from
normal to the cap. Two subtleties:

- The load fee is **per node**. A transaction must satisfy the
  load-scaled minimum of a majority of validators, so loading one node
  does not raise the network minimum.
- The live node reports load factor 256 (no load), so this mechanism is
  entirely dormant on the testnet today.

## 5. Sustained load: what the pinned algorithm does across ledgers

`FeeMetrics::update` (TxQ.cpp:85-168) runs at every ledger close:

- **Healthy ledger above target:** `txnsExpected` grows toward
  (ledger size x 1.2), tracked over the last 20 ledgers; it shrinks only
  slowly (90% drift) when the recent maximum falls.
- **Slow-consensus ledger:** `txnsExpected` is halved (floor 32) and the
  recent history is cleared.
- **Idle ledger (0 transactions):** nothing changes — neither branch runs.
- **Multiplier:** the median fee level of the closed ledger becomes the
  next ledger's escalation multiplier, floored at 128000.

The simulation in `src/fee_model.py` re-implements this exactly
(including integer truncation) for four scenarios:

- **Idle, 20 ledgers:** `txnsExpected` stays 32, multiplier stays
  128000. The floor state is a fixed point.
- **Flood, 100 txs/ledger, 20 ledgers:** `txnsExpected` rises to 120
  after the first ledger and stays there; the multiplier compounds about
  2.4x per ledger (128000 -> 306,313 -> 733,027 -> 1,754,182 ...),
  reaching ~4.9 x 10^12 by ledger 20. The fee for the first escalated
  transaction in the next ledger exceeds the entire 100-billion-PFT
  supply within a few ledgers.
- **Flood, 1000 txs/ledger, 5 ledgers:** `txnsExpected` rises to 1200;
  the multiplier reaches ~1.1 x 10^17 by ledger 5.
- **Flood then one slow-consensus ledger:** `txnsExpected` is cut from
  1200 to 500 by the slow ledger, then rebuilds to 1200 on the next
  healthy flood ledger.

Two consequences follow, and both are in the gap register (F-11, F-01):

1. **A sustained flood is self-defeating for the attacker and
   self-harming for everyone else.** The compounding median makes the
   open ledger unaffordable within a few ledgers, so further transactions
   queue instead of entering the ledger — which is the design working —
   but a slow-consensus ledger halves the cheap-transaction allowance for
   legitimate users at the same time.
2. **The allowance does not decay on idle ledgers.** After a flood,
   `txnsExpected` stays elevated indefinitely until a slow ledger cuts
   it. That is good for legitimate users (more cheap capacity after the
   attack) and good for the next attacker (a higher starting allowance).

## 6. Per-endpoint resource charges (RPC layer)

The node charges every inbound request against the requesting endpoint's
balance (Fees.cpp:26-44), warns at 5000 and disconnects at 25000
(Tuning.h:31-44), with balances decaying over a 32-second window. Worst
case inside one decay window (ignoring decay):

| Request class | Charge | Requests to warn (5000) | Requests to drop (25000) |
| --- | --- | --- | --- |
| Reference RPC | 20 | 250 | 1,250 |
| Medium-burden RPC | 400 | 13 | 63 |
| Heavy-burden RPC | 3000 | 2 | 9 |
| Invalid signature | 2000 | 3 | 13 |

A slow trickle never reaches either threshold because of the decay. These
numbers describe the node's peer layer; whether the public HTTPS proxy
applies the same charges is unobservable from outside (finding F-07).
