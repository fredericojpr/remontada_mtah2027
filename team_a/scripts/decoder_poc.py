"""Proof of concept: is a temporal decoder a free win over the baseline's majority vote?

Same per-frame signal as the baseline -- the nearest tracked player's team, with a missing ball
treated as no observation -- decoded by a 2-state (H/A) Viterbi instead. Never writes D.

The signal is read back from evaluation/results/baseline_raw.csv, which is the baseline's
per-frame output (D there means exactly "ATD ball is NaN"), so this needs no gated data.

Parameters are round a-priori numbers, NOT tuned on the public window. Two evidence
temperatures are shown because they bracket the failure modes; no sweep was run.

    python team_a/scripts/decoder_poc.py
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

RESULTS = os.path.join(ROOT, "evaluation", "results")
GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
HALVES = ((11185, 90652), (110808, 190198))

# Params
P_SWITCH = 1.0 / (25 * 10)  # prior: possessions last ~10 s
ACCURACY = 0.75             # prior: nearest player names the right team 3 times in 4
TEMPERATURES = ((1.0, "per-frame evidence (independent)"),
                (1.0 / 25, "evidence tempered to ~1 obs per second"))


def viterbi(obs, p_switch, accuracy, temperature):
    """Most likely H/A path. obs: 0=H, 1=A, anything else = ball not seen."""
    log_trans = np.log(np.array([[1 - p_switch, p_switch], [p_switch, 1 - p_switch]]))
    log_emit = temperature * np.log(np.array([[accuracy, 1 - accuracy],
                                              [1 - accuracy, accuracy]]))
    score = np.log([0.5, 0.5])
    back = np.zeros((len(obs), 2), dtype=np.int8)
    for t in range(len(obs)):
        candidates = score[:, None] + log_trans
        back[t] = np.argmax(candidates, axis=0)
        score = candidates[back[t], [0, 1]]
        if obs[t] in (0, 1):
            score = score + log_emit[:, obs[t]]
    path = np.zeros(len(obs), dtype=np.int8)
    path[-1] = np.argmax(score)
    for t in range(len(obs) - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def report(name, gt, pred):
    r = pm.evaluate(gt, pred, bootstrap_n=1000)
    print("{:<46} spellF1 {:.3f} [{:.3f}-{:.3f}]  macroF1 {:.3f}  poss {:>3}  dur {:>5.1f} s".format(
        name, r["spell_f1_mean"], r["spell_bootstrap_low"], r["spell_bootstrap_high"],
        r["macro_f1"], r["n_pred_spells"], r["mean_spell_duration_s"]))


if __name__ == '__main__':
    gt = pm.label_codes(pm.read_label_csv(GT_PATH))
    raw = pm.label_codes(pm.read_label_csv(os.path.join(RESULTS, "baseline_raw.csv")))
    floor = pm.label_codes(pm.read_label_csv(os.path.join(RESULTS, "baseline_smooth50.csv")))

    print("ground truth: 17 possessions, mean 14.2 s\n")
    report("baseline_smooth50 (published floor)", gt, floor)
    for temperature, label in TEMPERATURES:
        pred = np.full(len(gt), pm.X, dtype=np.int8)
        for a, b in HALVES:
            pred[a:b] = viterbi(raw[a:b], P_SWITCH, ACCURACY, temperature)
        report("Viterbi, " + label, gt, pred)
