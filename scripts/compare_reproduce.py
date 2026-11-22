#!/usr/bin/env python3
"""compare_reproduce.py — compare a fresh reproduction against the shipped pack.

Usage:
  python3 scripts/compare_reproduce.py SHIPPED_DERIVED_DIR FRESH_DERIVED_DIR

Compares the derived numbers that must be stable across runs (fee levels,
queue limits, reserves, model outputs) and the numbers that must only move
in the expected direction (ledger sequence increases, burned total does not
decrease). Prints one PASS/FAIL line per check plus an overall line, and
exits 0 only if every check passes.

Fee levels, queue sizes, and model outputs are deterministic functions of
the pinned constants and must match exactly. Ledger sequence, total coins,
and cadence move with the live network and are checked with tolerances.
"""
import json
import os
import sys


def load(d, name):
    with open(os.path.join(d, name)) as f:
        return json.load(f)


def main():
    shipped_dir, fresh_dir = sys.argv[1], sys.argv[2]
    shipped_live = load(shipped_dir, "live-fee-market.json")
    fresh_live = load(fresh_dir, "live-fee-market.json")
    shipped_model = load(shipped_dir, "escalation-model.json")
    fresh_model = load(fresh_dir, "escalation-model.json")
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))

    sf, ff = shipped_live["fee"], fresh_live["fee"]
    for key in ("base_fee_drops", "median_fee_drops", "minimum_fee_drops",
                "open_ledger_fee_drops", "median_level", "minimum_level",
                "open_ledger_level", "reference_level", "expected_ledger_size",
                "max_queue_size"):
        check("fee.%s == %s" % (key, sf[key]), str(ff[key]) == str(sf[key]),
              "(shipped=%s fresh=%s)" % (sf[key], ff[key]))
    check("fee.current_queue_size == 0", ff["current_queue_size"] in ("0", 0),
          "(fresh=%s)" % ff["current_queue_size"])
    check("validated seq increased",
          fresh_live["validated_ledger_seq"] > shipped_live["validated_ledger_seq"],
          "(shipped=%s fresh=%s)" % (shipped_live["validated_ledger_seq"],
                                      fresh_live["validated_ledger_seq"]))
    check("network_id == 2025", fresh_live["network_id"] == 2025,
          "(fresh=%s)" % fresh_live["network_id"])
    check("build_version == 1.0.9", fresh_live["build_version"] == "1.0.9",
          "(fresh=%s)" % fresh_live["build_version"])
    check("load factors all 256",
          all(str(v) == "256" for v in fresh_live["load_factors_server_state"].values()),
          "(fresh=%s)" % fresh_live["load_factors_server_state"])
    check("burned_pft did not decrease",
          fresh_live["burned_pft"] >= shipped_live["burned_pft"],
          "(shipped=%.6f fresh=%.6f)" % (shipped_live["burned_pft"], fresh_live["burned_pft"]))
    check("reserves unchanged",
          fresh_live["reserves_drops"] == shipped_live["reserves_drops"],
          "(fresh=%s)" % fresh_live["reserves_drops"])
    cad = fresh_live["fee_timeseries"]["mean_close_interval_s"]
    check("mean close interval 2.5-4.0 s", cad is not None and 2.5 <= cad <= 4.0,
          "(fresh=%s)" % cad)
    check("timeseries samples all ok",
          fresh_live["fee_timeseries"]["errors"] == 0,
          "(errors=%s)" % fresh_live["fee_timeseries"]["errors"])
    check("timeseries queue always 0",
          fresh_live["fee_timeseries"]["distinct_current_queue_size"] == ["0"],
          "(fresh=%s)" % fresh_live["fee_timeseries"]["distinct_current_queue_size"])
    check("model escalation_curve identical",
          fresh_model["escalation_curve"] == shipped_model["escalation_curve"])
    check("model queue identical",
          fresh_model["queue"] == shipped_model["queue"])
    check("model cumulative fill costs identical",
          fresh_model["cumulative_open_ledger_fill_cost"] ==
          shipped_model["cumulative_open_ledger_fill_cost"])
    check("model resource charges identical",
          fresh_model["resource_charges"] == shipped_model["resource_charges"])
    check("model sustained scenarios identical",
          fresh_model["sustained_load_dynamics"] == shipped_model["sustained_load_dynamics"])
    check("ledger-load mean < 5 tx/ledger",
          fresh_live["ledger_load_sample"]["mean_txns_per_ledger"] < 5,
          "(fresh mean=%.3f)" % fresh_live["ledger_load_sample"]["mean_txns_per_ledger"])

    n_pass = sum(1 for _, ok, _ in checks if ok)
    print("compare_reproduce.py: %d/%d CHECKS PASSED" % (n_pass, len(checks)))
    if n_pass != len(checks):
        print("compare_reproduce.py: COMPARISON FAILED")
        return 1
    print("compare_reproduce.py: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
