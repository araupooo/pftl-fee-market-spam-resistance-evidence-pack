#!/usr/bin/env python3
"""extract_excerpts.py — copy verbatim pinned-source excerpts into fixtures/.

Usage:
  python3 scripts/extract_excerpts.py [CLONE_DIR]
    CLONE_DIR defaults to ../work/postfiatd-pinned relative to the task folder
    (two levels above the pack). The script verifies the clone is at the
    pinned commit before extracting anything.

Each excerpt file starts with a header giving the pinned commit, the file
path, and the exact line range, so a reader can check it with grep -n.
fixtures/source-hashes.json records the git blob SHA-1 of every cited file
at the pinned commit.
"""
import json
import os
import subprocess
import sys

PINNED = "0085a1ff885d6a446369cf73a4430f75af22be55"

EXCERPTS = [
    # (source path in repo, first line, last line, output name)
    ("src/xrpld/app/misc/TxQ.h", 60, 160, "TxQ-Setup.txt"),
    ("src/xrpld/app/misc/TxQ.h", 375, 420, "TxQ-FeeMetrics-ctor.txt"),
    ("src/xrpld/app/misc/TxQ.h", 575, 585, "TxQ-retriesAllowed.txt"),
    ("src/xrpld/app/misc/detail/TxQ.cpp", 85, 195, "TxQ-FeeMetrics-update-scaleFeeLevel.txt"),
    ("src/xrpld/app/misc/detail/TxQ.cpp", 1240, 1330, "TxQ-queue-full-eviction.txt"),
    ("src/xrpld/app/misc/detail/TxQ.cpp", 1777, 1800, "TxQ-getMetrics.txt"),
    ("src/xrpld/app/misc/detail/TxQ.cpp", 1860, 1913, "TxQ-doRPC.txt"),
    ("src/xrpld/app/misc/detail/TxQ.cpp", 1914, 1982, "TxQ-setup_TxQ.txt"),
    ("src/xrpld/app/misc/LoadFeeTrack.h", 139, 150, "LoadFeeTrack-constants.txt"),
    ("src/xrpld/app/misc/detail/LoadFeeTrack.cpp", 28, 112, "LoadFeeTrack-raise-lower-scale.txt"),
    ("src/xrpld/app/misc/FeeEscalation.md", 1, 90, "FeeEscalation-fee-escalation.txt"),
    ("src/xrpld/app/misc/FeeEscalation.md", 90, 155, "FeeEscalation-transaction-queue.txt"),
    ("src/xrpld/app/misc/FeeEscalation.md", 224, 281, "FeeEscalation-other-constants.txt"),
    ("src/xrpld/app/misc/FeeEscalation.md", 282, 323, "FeeEscalation-fee-command.txt"),
    ("src/libxrpl/resource/Fees.cpp", 20, 49, "resource-fees.txt"),
    ("include/xrpl/resource/detail/Tuning.h", 24, 50, "resource-tuning.txt"),
    ("src/xrpld/core/Config.h", 60, 80, "Config-FeeSetup.txt"),
    ("src/xrpld/app/tx/detail/Transactor.cpp", 370, 445, "Transactor-checkFee.txt"),
    ("src/xrpld/app/misc/FeeVoteImpl.cpp", 25, 92, "FeeVote-VotableValue.txt"),
    ("src/xrpld/app/ledger/Ledger.h", 420, 430, "Ledger-flag-interval.txt"),
    ("src/xrpld/app/misc/NetworkOPs.cpp", 2985, 2996, "NetworkOPs-server-info-load-fields.txt"),
]

HASHED_FILES = sorted({e[0] for e in EXCERPTS})


def main():
    pack = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    task = os.path.dirname(pack)
    clone = sys.argv[1] if len(sys.argv) > 1 else os.path.join(task, "work", "postfiatd-pinned")
    head = subprocess.check_output(["git", "-C", clone, "rev-parse", "HEAD"],
                                   text=True).strip()
    print("clone HEAD: %s" % head)
    assert head == PINNED, "clone is not at the pinned commit %s" % PINNED
    outdir = os.path.join(pack, "fixtures", "source-excerpts")
    os.makedirs(outdir, exist_ok=True)
    for rel, first, last, name in EXCERPTS:
        lines = open(os.path.join(clone, rel), encoding="utf-8", errors="replace").read().splitlines()
        assert 1 <= first <= last <= len(lines), (rel, first, last, len(lines))
        header = ("# Pinned source excerpt\n"
                  "# repo: https://github.com/postfiatorg/postfiatd\n"
                  "# commit: %s\n"
                  "# file: %s\n"
                  "# lines: %d-%d (1-based, verified with grep -n)\n"
                  "# ----\n" % (PINNED, rel, first, last))
        body = "\n".join("%d: %s" % (i, lines[i - 1]) for i in range(first, last + 1))
        with open(os.path.join(outdir, name), "w") as f:
            f.write(header + body + "\n")
        print("wrote fixtures/source-excerpts/%s (%s:%d-%d)" % (name, rel, first, last))
    hashes = {}
    for rel in HASHED_FILES:
        blob = subprocess.check_output(["git", "-C", clone, "hash-object", rel],
                                       text=True).strip()
        hashes[rel] = blob
    with open(os.path.join(pack, "fixtures", "source-hashes.json"), "w") as f:
        json.dump({"pinned_commit": PINNED,
                   "repo": "https://github.com/postfiatorg/postfiatd",
                   "git_blob_sha1": hashes}, f, indent=1)
    print("wrote fixtures/source-hashes.json (%d files)" % len(hashes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
