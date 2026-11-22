#!/usr/bin/env python3
"""fee_model.py — fee-escalation and spam-cost model from pinned constants.

Pure computation: no network access, no transactions. Every number derives
from the pinned protocol parameters in configs/fee-parameters.json, which
cite the pinned postfiatd revision (see fixtures/source-hashes.json).

Model (see docs/escalation-model.md for the derivation):
  * Reference transaction: base fee 10 drops, base fee level 256.
  * Open-ledger fee level for n transactions already in the open ledger:
        level(n) = 256                                  if n <= target
        level(n) = median_level * n^2 / target^2        if n > target
    where target = txnsExpected (32 live, the minimumTxnInLedger floor) and
    median_level = 128000 (the minimumEscalationMultiplier floor, live).
    Drops for a reference transaction: level * 10 / 256, rounded UP (the
    node adds 1 drop when the rounded value would fall below the level;
    see TxQ::doRPC).
  * Queue capacity: max(txnsExpected * ledgersInQueue, queueSizeMin)
    = max(32 * 20, 2000) = 2000.
  * Queue-fill fee cost: 2000 slots at the minimum fee of 10 drops.
  * Queue-fill Sybil cost: 10 transactions max per account, so >= 200
    accounts; each account holds the 10 PFT account reserve.
  * Server-local load fee: starts at factor 256, +25% per raise event,
    capped at 256 * 1,000,000; minimum fee for a reference transaction is
    base fee * factor / 256.
  * Resource charges: a heavy-burden RPC costs 3000 charge units against a
    per-endpoint balance that warns at 5000 and disconnects at 25000, with
    a 32 s exponential decay window.

Usage:
  python3 src/fee_model.py [--params configs/fee-parameters.json]
      [--out outputs/derived/escalation-model.json]
      [--table fixtures/escalation-model-table.csv]
"""
import argparse
import csv
import json
import math
import os
import sys


def ceil_div(a, b):
    return -(-a // b)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    pack = os.path.dirname(here)
    ap.add_argument("--params", default=os.path.join(pack, "configs", "fee-parameters.json"))
    ap.add_argument("--out", default=os.path.join(pack, "outputs", "derived", "escalation-model.json"))
    ap.add_argument("--table", default=os.path.join(pack, "fixtures", "escalation-model-table.csv"))
    args = ap.parse_args()

    with open(args.params) as f:
        p = json.load(f)
    c = p["constants"]
    live = p["live_values_at_probe_time"]
    base_fee = c["reference_fee_drops"]          # 10
    base_level = c["base_fee_level"]             # 256
    target = live["txns_expected_live"]             # 32
    median_level = live["median_level_live"]        # 128000
    queue_min = c["queue_size_min"]              # 2000
    ledgers_in_queue = c["ledgers_in_queue"]     # 20
    max_per_account = c["maximum_txn_per_account"]  # 10
    reserve = c["account_reserve_drops"]         # 10,000,000

    def open_ledger_level(n):
        if n <= target:
            return base_level
        return median_level * n * n // (target * target)

    def open_ledger_fee_drops(n):
        # drops = level * base_fee / base_level, rounded up (node behaviour)
        return ceil_div(open_ledger_level(n) * base_fee, base_level)

    # --- Escalation curve: fee for the (n+1)-th transaction, n in ledger ---
    curve = []
    for n in [0, 1, 5, 10, 20, 31, 32, 33, 35, 40, 50, 64, 80, 100, 128, 200, 256, 512, 1000]:
        curve.append({"txns_in_open_ledger": n,
                      "fee_level_for_next_tx": open_ledger_level(n),
                      "fee_drops_for_next_reference_tx": open_ledger_fee_drops(n)})

    # --- Cumulative cost to fill the open ledger with n reference txs,
    #     each paying exactly the escalated minimum at its position ---
    def cumulative_fill_cost(n):
        return sum(open_ledger_fee_drops(k) for k in range(n))

    fill_costs = [{"txns_in_open_ledger": n,
                   "cumulative_minimum_fee_drops": cumulative_fill_cost(n),
                   "cumulative_minimum_fee_pft": cumulative_fill_cost(n) / 1_000_000}
                  for n in [33, 40, 50, 64, 100, 256, 512]]

    # --- Queue model ---
    queue_capacity = max(target * ledgers_in_queue, queue_min)
    queue_fill_fee_drops = queue_capacity * base_fee
    accounts_to_fill_queue = -(-queue_capacity // max_per_account)
    reserve_to_fill_queue_drops = accounts_to_fill_queue * reserve

    # --- Server-local load fee (LoadFeeTrack) ---
    load = {"normal_factor": c["load_factor_normal"],
            "increase_fraction": c["load_fee_inc_fraction"],
            "decrease_fraction": c["load_fee_dec_fraction"],
            "max_factor": c["load_factor_normal"] * c["load_fee_max_multiplier"],
            "max_multiplier_vs_base": c["load_fee_max_multiplier"],
            "max_minimum_fee_drops_reference_tx":
                base_fee * c["load_fee_max_multiplier"],
            "raises_to_reach_max_from_normal":
                math.ceil(math.log(c["load_fee_max_multiplier"]) /
                          math.log(1 + 1 / c["load_fee_inc_fraction"]))}

    # --- Resource-charge model (per-endpoint, 32 s decay window) ---
    charges = c["resource_charges"]
    warn = c["resource_warning_threshold"]
    drop = c["resource_drop_threshold"]
    resource = {
        "warning_threshold": warn, "drop_threshold": drop,
        "decay_window_seconds": c["resource_decay_window_seconds"],
        "heavy_rpc_requests_to_warn": -(-warn // charges["feeHeavyBurdenRPC"]),
        "heavy_rpc_requests_to_drop": -(-drop // charges["feeHeavyBurdenRPC"]),
        "reference_rpc_requests_to_warn": -(-warn // charges["feeReferenceRPC"]),
        "reference_rpc_requests_to_drop": -(-drop // charges["feeReferenceRPC"]),
        "invalid_signature_requests_to_drop": -(-drop // charges["feeInvalidSignature"]),
        "note": "Counts ignore decay: with the 32 s exponential decay window, "
                "a slow trickle never reaches either threshold; the counts are "
                "the worst case for a burst inside one decay window.",
    }

    # --- Sustained-load dynamics: faithful simulation of the pinned
    #     FeeMetrics::update algorithm (TxQ.cpp), assuming every transaction
    #     in a ledger pays exactly the escalated minimum for its position.
    #     Fee levels of a ledger are the per-position levels; the median of
    #     those levels becomes the next ledger's multiplier (floored at
    #     128000). Integer division follows the C++ code (truncating).
    # ---
    # Cap fee levels at the uint64 maximum, as the C++ mulDiv does
    # (scaleFeeLevel returns ripple::muldiv_max on overflow).
    UINT64_MAX = (1 << 64) - 1

    def level_for(n, mult):
        if n <= target:
            return base_level
        return min(mult * n * n // (target * target), UINT64_MAX)

    def simulate(ledger_sizes, slow_flags=None):
        expected = c["minimum_txn_in_ledger"]  # txnsExpected_ starts at the floor
        recent = []  # circular buffer, capacity ledgers_in_queue (20)
        multiplier = c["minimum_escalation_multiplier"]  # 128000
        history = []
        for i, size in enumerate(ledger_sizes):
            slow = bool(slow_flags and slow_flags[i])
            # Fee levels paid in THIS ledger use the multiplier in force at
            # its start (the previous ledger's median, floored at 128000).
            start_mult = multiplier
            if slow:
                cut = 100 - c["slow_consensus_decrease_percent"]  # 50
                upper = max(expected * cut // 100, c["minimum_txn_in_ledger"])
                expected = min(max(size * cut // 100, c["minimum_txn_in_ledger"]), upper)
                expected = max(expected, c["minimum_txn_in_ledger"])
                recent = []
            elif size > expected or size > c["target_txn_in_ledger"]:
                recent.append(size * (100 + c["normal_consensus_increase_percent"]) // 100)
                recent = recent[-c["ledgers_in_queue"]:]
                m = max(recent)
                nxt = m if m >= expected else (expected * 9 + m) // 10
                expected = nxt  # no maximumTxnInLedger configured on testnet
            if size == 0:
                multiplier = c["minimum_escalation_multiplier"]
            else:
                levels = sorted(level_for(k, start_mult) for k in range(size))
                med = (levels[size // 2] + levels[(size - 1) // 2] + 1) // 2
                multiplier = max(med, c["minimum_escalation_multiplier"])
                multiplier = min(multiplier, UINT64_MAX)
            next_fee_level = level_for(expected + 1, multiplier)
            history.append({"ledger": i, "txns": size, "slow_consensus": slow,
                            "txns_expected_after": expected,
                            "escalation_multiplier_after": multiplier,
                            "fee_level_for_tx_after_expected": next_fee_level,
                            "fee_drops_for_tx_after_expected": ceil_div(next_fee_level * base_fee, base_level)})
        return history

    sustained = {
        "algorithm": "FeeMetrics::update (TxQ.cpp), healthy growth +20%, "
                     "slow-consensus cut -50%, floor 32, median-of-ledger "
                     "multiplier floored at 128000",
        "scenario_idle_20_ledgers": simulate([0] * 20),
        "scenario_flood_100_per_ledger_20_ledgers": simulate([100] * 20),
        "scenario_flood_1000_per_ledger_5_ledgers": simulate([1000] * 5),
        "scenario_flood_then_slow_consensus": simulate(
            [1000, 1000, 1000], [False, True, False]),
        "note": "Idle ledgers change nothing: with 0 transactions neither "
                "the growth nor the cut branch runs, so txnsExpected stays "
                "where the last busy ledger left it until a slow-consensus "
                "ledger halves it. The cheap-transaction allowance therefore "
                "stays elevated after a flood, which helps legitimate users "
                "but also gives the next flood a higher starting allowance. "
                "The flood scenarios assume the attacker pays the escalated "
                "minimum at every position in every ledger (worst-case "
                "willingness to pay). Under that assumption the multiplier "
                "compounds ~2.4x per 100-tx ledger, and the required fee "
                "exceeds the entire 100-billion-PFT supply within a few "
                "ledgers. In practice nobody can pay that, so transactions "
                "queue instead of entering the ledger and the multiplier "
                "stops compounding: the queue, not the open ledger, absorbs "
                "a sustained flood. Fee levels are capped at the uint64 "
                "maximum, as the C++ mulDiv does.",
    }

    model = {
        "inputs": {"params_file": args.params, "constants": c},
        "escalation_curve": curve,
        "cumulative_open_ledger_fill_cost": fill_costs,
        "queue": {
            "capacity_txns": queue_capacity,
            "fill_fee_cost_drops": queue_fill_fee_drops,
            "fill_fee_cost_pft": queue_fill_fee_drops / 1_000_000,
            "accounts_needed_to_fill_queue": accounts_to_fill_queue,
            "reserve_locked_to_fill_queue_drops": reserve_to_fill_queue_drops,
            "reserve_locked_to_fill_queue_pft": reserve_to_fill_queue_drops / 1_000_000,
        },
        "server_local_load_fee": load,
        "resource_charges": resource,
        "sustained_load_dynamics": sustained,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(model, f, indent=1)
    with open(args.table, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["txns_in_open_ledger", "fee_level_for_next_tx",
                    "fee_drops_for_next_reference_tx"])
        for row in curve:
            w.writerow([row["txns_in_open_ledger"], row["fee_level_for_next_tx"],
                        row["fee_drops_for_next_reference_tx"]])
    print("fee_model.py: wrote %s and %s" % (args.out, args.table))
    print("  open-ledger fee: n=32 -> %d drops, n=33 -> %d drops, "
          "n=64 -> %d drops, n=100 -> %d drops, n=256 -> %d drops" % (
              open_ledger_fee_drops(32), open_ledger_fee_drops(33),
              open_ledger_fee_drops(64), open_ledger_fee_drops(100),
              open_ledger_fee_drops(256)))
    print("  fill 100 txs: %d drops (%.6f PFT); fill 256 txs: %d drops (%.6f PFT)" % (
        cumulative_fill_cost(100), cumulative_fill_cost(100) / 1e6,
        cumulative_fill_cost(256), cumulative_fill_cost(256) / 1e6))
    print("  queue capacity %d; fill fee %d drops; accounts to fill %d; "
          "reserve locked %d drops (%.0f PFT)" % (
              queue_capacity, queue_fill_fee_drops, accounts_to_fill_queue,
              reserve_to_fill_queue_drops, reserve_to_fill_queue_drops / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
