"""Cost of ONE error of each kind on spellF1 (and macroF1), averaged over every place it could occur.

metric_sensitivity.py injects many defects at once, so its rows mix the cost of an error with
how many of them were injected. This script injects exactly one, at every eligible location,
and reports the mean drop from a perfect 1.0. On 17 possessions one fully lost possession is
worth about 1/17 = 0.059, which is the scale to read these against.

    python team_a/scripts/per_error_cost.py
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
H, A, D, X = pm.H, pm.A, pm.D, pm.X
N_RANDOM = 200

gt = pm.label_codes(pm.read_label_csv(GT_PATH))
runs = pm.valid_runs(gt)
segs = pm.segments(gt, runs)
spells = [(a, b, c) for a, b, c in segs if c in (H, A)]
long_spells = [(a, b, c) for a, b, c in spells if b - a > 200]
short_spells = [(a, b, c) for a, b, c in spells if b - a < 100]
stoppages = [(a, b, c) for a, b, c in segs if c == D]


def cost(pred):
    """(spellF1 cost, macroF1 cost) against a perfect 1.0."""
    result = pm.evaluate(gt, pred)
    return 1.0 - result["spell_f1_mean"], 1.0 - result["macro_f1"]


def other(code):
    return A if code == H else H


def random_inside(rng, width):
    a, b, _ = long_spells[rng.randint(len(long_spells))]
    start = rng.randint(a + 20, b - width - 20)
    return start, start + width


def blip(rng):
    pred = gt.copy()
    start, stop = random_inside(rng, 10)
    pred[start:stop] = other(gt[start])
    return pred


def false_stoppage(rng):
    pred = gt.copy()
    start, stop = random_inside(rng, 25)
    pred[start:stop] = D
    return pred


def report(name, costs):
    costs = np.asarray(costs)
    spell, macro = costs[:, 0], costs[:, 1]
    print("{:<52} n={:>3}  spellF1 mean {:.3f}  range {:.3f}-{:.3f}  |  macroF1 mean {:.4f}".format(
        name, len(costs), spell.mean(), spell.min(), spell.max(), macro.mean()))


if __name__ == '__main__':
    print("reference: one possession of 17 = {:.3f}\n".format(1.0 / len(spells)))

    report("1 spurious 10-frame blip inside a possession > 8 s",
           [cost(blip(np.random.RandomState(s))) for s in range(N_RANDOM)])
    report("1 false 1 s stoppage inside a possession > 8 s",
           [cost(false_stoppage(np.random.RandomState(s))) for s in range(N_RANDOM)])

    missed_stoppage = []
    for a, b, _ in stoppages:
        pred = gt.copy()
        pred[a:b] = X
        missed_stoppage.append(cost(pm.fill_abstentions(pred, runs)))
    report("1 real stoppage missed (previous team carried)", missed_stoppage)

    missed_short = []
    for a, b, _ in short_spells:
        pred = gt.copy()
        pred[a:b] = X
        missed_short.append(cost(pm.fill_abstentions(pred, runs)))
    report("1 possession < 4 s missed (absorbed)", missed_short)

    wrong_team = []
    for a, b, c in spells:
        pred = gt.copy()
        pred[a:b] = other(c)
        wrong_team.append(cost(pred))
    report("1 whole possession given to the wrong team", wrong_team)

    late = []
    for f, _, _ in pm.transitions(gt, runs):
        pred = gt.copy()
        pred[f:f + 25] = gt[f - 1]
        late.append(cost(pred))
    report("1 transition 1 s late", late)
