"""How late our rules restart play, by restart type, on the public Metrica Sample Game 3.

Rule 8 dates every restart by the first kick (the ball travels 1.5 m within 0.5 s). On our match
the 2nd-half kickoff came out 3.4 s late with the ball tracked throughout (SIGNOFF section 8), so
this asks whether short restarts are late in general. Another game, so allowed; nothing here
reads our match.

For each SET PIECE event (frame of the event = the true restart) it finds our dead stretch over
the true one and reports our restart minus the true one, in seconds. "Tap" means the ball, as
tracked on the clean sample, moves less than the kick distance within the kick window after the
restart. "Ball gap" means the ball, in the tracking being labelled, is missing somewhere in the
kick window after the restart. Run on the clean sample and on the degraded one
(team_a/degrade.py).

It compares rule 8 with and without gap-backdated restarts. The sample's ball is blank whenever
play is dead, so the third proxy fills it in first (degrade.fill_dead_ball): only that one can
show whether backdating helps, because on the other two nearly every restart follows a gap.

    python team_a/scripts/restart_latency.py [--by-type]
"""

import dataclasses
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
from team_a import degrade, possession, sample_game as sg  # noqa: E402
from team_a.config import DEFAULT, FPS  # noqa: E402
from team_a.evidence import runs  # noqa: E402
import possession_metrics as pm  # noqa: E402

SEARCH_AFTER = 5 * FPS
LATE = 1 * FPS


def restarts(events):
    """[(frame, type, period opener)] for every set piece, frames 0-based like the labels."""
    first = {}
    for e in events:
        first[e["period"]] = min(first.get(e["period"], e["start"]["frame"]), e["start"]["frame"])
    out = []
    for e in events:
        if e["type"]["name"] != "SET PIECE":
            continue
        sub = sg.subtypes(e) - {"RETAKEN", "DIRECT", "INDIRECT"}
        out.append((e["start"]["frame"] - 1, "/".join(sorted(sub)) or "OTHER",
                    e["start"]["frame"] == first[e["period"]]))
    return out


def ball_travel(ball, frame, params):
    """Largest distance the ball gets from its restart position within the kick window."""
    start = ball[frame]
    if np.isnan(start[0]):
        return np.nan
    window = ball[frame + 1:frame + 1 + params.kick_window_frames]
    with np.errstate(invalid="ignore"):
        return np.nanmax(np.hypot(*(window - start).T)) if np.any(~np.isnan(window[:, 0])) \
            else np.nan


def latency(pred, gt, frame):
    """Our restart minus the true one, in frames, or None if we have no dead stretch there."""
    true_dead = {stop: start for start, stop in runs(gt == pm.D)}
    since = true_dead.get(frame, frame)
    ours = [(a, b) for a, b in runs(pred == pm.D) if a < frame + SEARCH_AFTER and b > since]
    if not ours:
        return None
    return min((b - frame for _, b in ours), key=abs)


def summary(name, values):
    found = np.array([v for v in values if v is not None], dtype=float)
    missed = len(values) - len(found)
    if not len(found):
        return "  {:<26} n {:>3}  no stoppage found {:>3}".format(name, len(values), missed)
    q1, med, q3 = np.percentile(found, [25, 50, 75]) / FPS
    return ("  {:<26} n {:>3}  no stoppage found {:>3}  median {:+5.1f} s  [{:+5.1f} {:+5.1f}]  "
            "> 1 s late {:>3.0f}%  > 1 s early {:>3.0f}%".format(
                name, len(values), missed, med, q1, q3, 100 * np.mean(found > LATE),
                100 * np.mean(found < -LATE)))


def report(name, gt, pred, events, travel, gap, by_type):
    lat = {f: latency(pred, gt, f) for f, _, _ in events}
    r = pm.evaluate(gt, pred, bootstrap_n=1000)
    print("  {}: spellF1 {:.3f} [{:.3f}-{:.3f}]  macroF1 {:.3f}  poss {} (truth {})".format(
        name, r["spell_f1_mean"], r["spell_bootstrap_low"], r["spell_bootstrap_high"],
        r["macro_f1"], r["n_pred_spells"], r["n_gt_spells"]))
    print(summary("all", list(lat.values())))
    if by_type:
        for kind in sorted({k for _, k, _ in events}):
            print(summary(kind, [lat[f] for f, k, _ in events if k == kind]))
        print(summary("period openers", [lat[f] for f, _, o in events if o]))
    print(summary("tap (< kick distance)",
                  [lat[f] for f in travel if travel[f] < DEFAULT.kick_distance_m]))
    print(summary("ball gap in kick window", [lat[f] for f in gap if gap[f]]))
    print(summary("ball seen in kick window", [lat[f] for f in gap if not gap[f]]))


if __name__ == '__main__':
    by_type = "--by-type" in sys.argv
    tracking = sg.load_tracking()
    n = len(tracking.frame_id)
    gt = sg.load_labels(n)
    halves = [(a, b - 1) for a, b in pm.valid_runs(gt)]
    events = restarts(sg.load_events())
    travel = {f: ball_travel(tracking.ball_xy, f, DEFAULT) for f, _, _ in events}

    taps = [f for f in travel if travel[f] < DEFAULT.kick_distance_m]
    unknown = [f for f in travel if np.isnan(travel[f])]
    print("{} restarts; ball travel in the first {:.2f} s on the clean sample: < {} m (tap) {}, "
          ">= {} m {}, ball unseen at the restart {}".format(
              len(events), DEFAULT.kick_window_frames / FPS, DEFAULT.kick_distance_m, len(taps),
              DEFAULT.kick_distance_m, len(events) - len(taps) - len(unknown), len(unknown)))

    proxies = [("clean", tracking), ("degraded", degrade.degrade(tracking)),
               ("degraded, dead ball filled",
                degrade.degrade(degrade.fill_dead_ball(tracking, gt)))]
    variants = [("restarts as before", dataclasses.replace(DEFAULT, restart_backdate_max_frames=0)),
                ("gap-backdated restarts", DEFAULT)]
    for name, data in proxies:
        gap = {f: np.isnan(data.ball_xy[f:f + 1 + DEFAULT.kick_window_frames, 0]).any()
               for f, _, _ in events}
        dead = gt == pm.D
        print("\n{} sample (ball seen on {:.0f}% of dead frames): our restart minus the true "
              "restart".format(name, 100 * np.mean(~np.isnan(data.ball_xy[dead, 0]))))
        for label, params in variants:
            report(label, gt, possession.label_match(data, halves, n, params=params), events,
                   travel, gap, by_type)
