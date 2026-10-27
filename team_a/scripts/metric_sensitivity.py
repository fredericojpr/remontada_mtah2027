"""How much does each kind of mistake cost on spellF1? Perturb the public ground truth and score it.

This is for understanding the metric, not for tuning a model: every "prediction" below is the
truth with one controlled defect injected. 17 possessions is a small sample, so read the numbers
as directions and orders of magnitude, not as precise costs.

    python team_a/scripts/metric_sensitivity.py
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
H, A, D, X = pm.H, pm.A, pm.D, pm.X
N_SEEDS = 50

gt = pm.label_codes(pm.read_label_csv(GT_PATH))
runs = pm.valid_runs(gt)
start, stop = runs[0]
segs = pm.segments(gt, runs)
long_spells = [(a, b, c) for a, b, c in segs if c in (H, A) and b - a > 200]


def score(pred):
    result = pm.evaluate(gt, pred)
    return result["spell_f1_mean"], result["macro_f1"], result["n_pred_spells"]


def show(name, pred):
    spell, macro, n = score(pred)
    print("{:<64} spellF1 {:.3f}  macroF1 {:.3f}  poss {:>3}".format(name, spell, macro, n))


def show_mean(name, make):
    values = [score(make(np.random.RandomState(seed)))[0] for seed in range(N_SEEDS)]
    print("{:<64} spellF1 {:.3f}  (mean of {} seeds)".format(name, np.mean(values), N_SEEDS))


def other(code):
    return A if code == H else H


def jittered(sd):
    def make(rng):
        bounds = [a for a, _, _ in segs[1:]]
        moved = sorted(int(np.clip(b + rng.normal(0, sd), start + 1, stop - 1)) for b in bounds)
        edges = [start] + moved + [stop]
        pred = gt.copy()
        for i, (_, _, k) in enumerate(segs):
            pred[edges[i]:edges[i + 1]] = k
        return pred
    return make


def blips(k):
    def make(rng):
        pred = gt.copy()
        for _ in range(k):
            a, b, c = long_spells[rng.randint(len(long_spells))]
            f = rng.randint(a + 20, b - 30)
            pred[f:f + 10] = other(c)
        return pred
    return make


def flipped(k):
    def make(rng):
        pred = gt.copy()
        spells = [(a, b, c) for a, b, c in segs if c in (H, A)]
        for i in rng.choice(len(spells), k, replace=False):
            a, b, c = spells[i]
            pred[a:b] = other(c)
        return pred
    return make


if __name__ == '__main__':
    show("perfect", gt.copy())

    for lag in (3, 8, 12, 25, 50):
        pred = gt.copy()
        pred[start + lag:stop] = gt[start:stop - lag]
        show("every boundary {} frames late ({:.2f} s)".format(lag, lag / 25.0), pred)

    for sd in (5, 12, 25):
        show_mean("every boundary jittered N(0, {} frames)".format(sd), jittered(sd))

    pred = gt.copy()
    pred[gt == D] = X
    show("no dead ball detected (D -> previous team carried)", pm.fill_abstentions(pred, runs))

    for seconds in (1, 2, 4):
        pred = gt.copy()
        for a, b, k in segs:
            if k in (H, A) and b - a < seconds * 25:
                pred[a:b] = X
        show("possessions shorter than {} s missed (absorbed)".format(seconds),
             pm.fill_abstentions(pred, runs))

    for k in (5, 10, 20):
        show_mean("{} spurious 10-frame opposite-team blips".format(k), blips(k))

    pred = gt.copy()
    for a, b, _ in long_spells:
        middle = (a + b) // 2
        pred[middle:middle + 25] = D
    show("1 s false stoppage inside every possession > 8 s", pred)

    for k in (1, 3):
        show_mean("{} whole possession(s) given to the wrong team".format(k), flipped(k))

    pred = gt.copy()
    for f, _, _ in pm.transitions(gt, runs):
        pred[f - 12:f + 12] = X
    show("X for +/-0.5 s around every true transition", pred)

    pred = gt.copy()
    for a, b, c in segs:
        if c in (H, A) and b - a > 100:
            pred[a + 40:b - 40] = X
    show("X in the interior of every possession > 4 s", pred)
