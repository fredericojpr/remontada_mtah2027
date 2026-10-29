"""Regenerate the submission from the provided data.

    MTAH_DATA_DIR=<data folder> python -m team_a.pipeline --out <team_name>.csv

Prints the validator result, aggregate counts, a correctness check against the public 5 minutes
(never used to choose between versions) and the file's sha256. No data values are printed.
"""

import argparse
import hashlib
import os
import sys

import numpy as np

from team_a import epts, possession

ROOT = epts.ROOT
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
sys.path.insert(0, os.path.join(ROOT, "starter"))
import baseline  # noqa: E402
import games  # noqa: E402
import possession_metrics as pm  # noqa: E402

PUBLIC_GT = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
PUBLISHED_SECOND_HALF_KICKOFF = 113742
KICKOFF_TOLERANCE_FRAMES = 50


def build(params=None):
    tracking = epts.load_match("tactical")
    halves = [(first, last) for _, first, last in games.half_video_blocks(games.GAME)]
    kwargs = {} if params is None else {"params": params}
    return possession.label_match(tracking, halves, games.source_frames("tactical"), **kwargs)


def write(labels, path):
    baseline.write_submission(path, np.array(pm.LABELS)[labels])
    reason = pm.validate_submission(pm.read_label_csv(path), games.source_frames("tactical"))
    return reason, hashlib.sha256(open(path, "rb").read()).hexdigest()


def summary(labels):
    runs = pm.valid_runs(np.where(labels == pm.X, pm.X, 0).astype(np.int8))
    segments = pm.segments(labels, runs)
    spells = [b - a for a, b, k in segments if k in (pm.H, pm.A)]
    stops = [b - a for a, b, k in segments if k == pm.D]
    second = games.half_video_blocks(games.GAME)[1][1]
    kickoff = next((b for a, b, k in segments if a == second and k == pm.D), second)
    return len(spells), np.mean(spells) / 25.0, len(stops), kickoff


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    labels = build()
    reason, digest = write(labels, args.out)
    print("validator  {}".format("OK" if reason is None else "FAIL: " + reason))

    n_spells, mean_s, n_stops, kickoff = summary(labels)
    print("possessions {}  mean {:.1f} s  stoppages {}".format(n_spells, mean_s, n_stops))
    near = abs(kickoff - PUBLISHED_SECOND_HALF_KICKOFF) <= KICKOFF_TOLERANCE_FRAMES
    print("2nd-half kickoff detected within 2 s of the published frame: {}".format(
        "PASS" if near else "FAIL"))

    gt = pm.label_codes(pm.read_label_csv(PUBLIC_GT))
    result = pm.evaluate(gt, labels, bootstrap_n=1000)
    print("public 5 min (correctness check only): spellF1 {:.3f} [{:.3f}-{:.3f}]  macroF1 {:.3f}  "
          "poss {} (truth {})".format(result["spell_f1_mean"], result["spell_bootstrap_low"],
                                      result["spell_bootstrap_high"], result["macro_f1"],
                                      result["n_pred_spells"], result["n_gt_spells"]))
    print("sha256  {}".format(digest))
