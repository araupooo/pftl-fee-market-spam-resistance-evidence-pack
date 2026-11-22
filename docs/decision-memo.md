# Decision memo — PFTL fee market and spam resistance

## Question

Is the PFTL fee market and spam-resistance design, as implemented in the
pinned postfiatd revision and as observed live on the testnet, adequate to
support a mainnet launch?

## Short answer

**Not yet proven — the design is sound on paper and untested in practice.**
The pinned code implements a coherent, layered defence (fee escalation,
transaction queue with eviction, per-account queue caps, server-local load
fees, per-endpoint resource charges, and a validator-voted base fee), and
every parameter of it is at its documented default on the testnet. But the
testnet is idle — 0 to 4 transactions per ledger, an empty queue, every fee
at its floor — so **no part of the defence has ever been observed working
under load**. A mainnet decision taken on this evidence alone would be
taken on code review, not on operational evidence.

## Evidence for the design (primary sources)

1. **Fee escalation is quadratic and starts with a cliff.** The first 32
   transactions in a ledger cost 10 drops each; the 33rd costs 5,318
   drops. The formula is pinned in code (TxQ.cpp:173-191) and matches the
   design document's own worked example (FeeEscalation.md: the 8th
   transaction at a level of about 174,000; the model gives 174,222).
2. **A single-ledger flood is expensive.** Filling one ledger with 256
   reference transactions at the escalated minimum costs 27.09 PFT, and a
   sustained flood compounds the median fee level ~2.4x per ledger until
   the required fee exceeds the entire token supply — at which point
   transactions queue instead (see docs/escalation-model.md §5).
3. **The queue is the shock absorber, and its cost is the reserve.**
   Filling the 2,000-slot queue costs 0.02 PFT in fees but locks 2,000 PFT
   across 200 accounts in reserves. The reserve, not the fee, is the
   Sybil control.
4. **Layered defences exist at three levels:** consensus (escalation +
   queue), per-node (server-local load fee up to 1,000,000x base), and
   per-endpoint (resource charges that warn at 5000 and disconnect at
   25000 over a 32-second decay window).
5. **No live anomaly.** Base fee 10 drops, median fee 5000 drops (a floor
   artifact — see finding F-02), queue 0/2000, load factors all at the 256
   reference, job-queue overflow 0, zero resource-driven peer
   disconnects, fee-burn accounting reconciles (33.454124 PFT burned
   against genesis supply).

## Evidence against readiness

1. **Zero live load events.** 4 transactions in 12 consecutive ledgers
   (mean 0.33); 0-4 transactions per validated ledger across a 20-sample,
   10-minute time series (mean 0.50); explorer reports 0.09 transactions
   per second. Nothing in this pack observes escalation, queueing,
   prioritisation, or eviction happening. Four claims are marked UNTESTABLE
   for exactly this reason.
2. **The median fee is a misleading signal.** At 5000 drops it looks like
   a market price; it is the code floor, because empty ledgers reset the
   multiplier to 128000. Any fee estimator using it overpays 500x.
3. **The public RPC proxy's rate-limit policy is unknown.** No rate-limit
   header is advertised, and the node's peer-layer resource charges cannot
   be confirmed to apply to the HTTPS proxy. A single client could, as far
   as this pack can determine, hammer the proxy with cheap reads.
4. **The queue-eviction averaging rule shelters cheap transactions.**
   Eviction compares against a victim account's average fee level, not its
   lowest fee, so a mixed-fee account's cheap transactions survive
   eviction that a single-transaction account's would not.
5. **The base fee cannot react inside a burst.** Fee votes happen only at
   flag ledgers, every 256 ledgers (~13 minutes), and only by validator
   majority.

## What would change the answer

- **Isolated-network load tests** (not on the shared testnet): fill the
  open ledger past 32 transactions, fill the queue to 2,000, and record
  the fee responses, the eviction order, and the median-fee ratchet. This
  is the single highest-value next step and it is the remediation for
  finding F-01.
- **A published proxy rate-limit policy** (finding F-07).
- **A fee-estimator fix** to use `open_ledger_fee`, not `median_fee`,
  while ledgers are empty (finding F-02).
- **A decision on the eviction averaging rule** (finding F-05) and on
  whether the account reserve stays at 10 PFT (finding F-03).

## Recommendation

Do not treat this pack as launch evidence. Treat it as the baseline: the
design is documented, the parameters are pinned, the live state is
measured, and the gaps are named. The next evidence pack for this topic
should be the isolated-network load test that turns finding F-01 and
claims C-24, C-25, and C-26 from UNTESTABLE into measured.

## Sources

Every factual statement above is traceable to `docs/claim-index.md`
(C-01 to C-30), `docs/citations.md`, and the verbatim excerpts in
`fixtures/source-excerpts/`. No statement in this memo relies on a source
outside this pack except the pinned repository itself and the live
endpoints listed in `run-manifest.json`.
