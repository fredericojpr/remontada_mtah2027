"""Dissect the public 5-minute ground truth: every segment, the transition mix, spell durations.

Reads only evaluation/gt/BAR-ATH_possession_gt_public.csv, which ships in the public repository,
so it needs no gated data.

    python team_a/scripts/gt_dissect.py
"""

import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
FPS = 25
KICKOFF = 11185


if __name__ == '__main__':
    gt = pm.label_codes(pm.read_label_csv(GT_PATH))
    runs = pm.valid_runs(gt)
    print("graded runs:", runs)

    segs = pm.segments(gt, runs)
    print("\n #  label   start    stop  frames    secs  t_from_kickoff_s")
    for i, (a, b, k) in enumerate(segs):
        print("{:>2}  {:>5}  {:>6}  {:>6}  {:>6}  {:>6.2f}  {:>8.1f}".format(
            i, pm.LABELS[k], a, b, b - a, (b - a) / float(FPS), (a - KICKOFF) / float(FPS)))

    trans = pm.transitions(gt, runs)
    print("\ntransition types:", dict(Counter(
        pm.LABELS[f] + ">" + pm.LABELS[t] for _, f, t in trans)))

    spells = pm.possession_spells(gt, runs)
    lengths = np.array([b - a for a, b, _ in spells]) / float(FPS)
    print("\npossessions: n={}  mean={:.1f}s  median={:.1f}s  min={:.1f}s  max={:.1f}s".format(
        len(lengths), lengths.mean(), np.median(lengths), lengths.min(), lengths.max()))
    print("sorted durations (s):", np.round(np.sort(lengths), 1).tolist())

    dead = np.array([b - a for a, b, k in segs if k == pm.D]) / float(FPS)
    print("dead-ball stretches: n={}  durations (s): {}".format(
        len(dead), np.round(dead, 1).tolist()))

    window = gt[runs[0][0]:runs[0][1]]
    print("label shares in window: H {:.1f}%  A {:.1f}%  D {:.1f}%".format(
        *[100.0 * np.mean(window == c) for c in (pm.H, pm.A, pm.D)]))
