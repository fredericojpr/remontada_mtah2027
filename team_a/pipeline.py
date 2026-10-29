"""Regenerate the submission from the provided data.

    MTAH_DATA_DIR=<data folder> python -m team_a.pipeline --out <team_name>.csv

Prints the validator result, aggregate counts, a correctness check against the public 5 minutes
(never used to choose between versions) and the file's sha256. No data values are printed.
"""

import argparse
import dataclasses
import hashlib
import os
import sys

import numpy as np

from team_a import epts, evidence, possession
from team_a.config import DEFAULT

ROOT = epts.ROOT
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
sys.path.insert(0, os.path.join(ROOT, "starter"))
import baseline  # noqa: E402
import games  # noqa: E402
import load_smart_tagging  # noqa: E402
import possession_metrics as pm  # noqa: E402

from team_a.dead_ball import kickoff_tag_starts  # noqa: E402

PUBLIC_GT = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
PUBLISHED_SECOND_HALF_KICKOFF = 113742
SUSTAINED_PLAY_FRAMES = 250
TOLERANCE_FRAMES = 50
PRE_KICKOFF_DEAD_SHARE = 0.9


def build(tracking, params=None, report=None, kickoff_tags=True):
    blocks = games.half_video_blocks(games.GAME)
    halves = [(first, last) for _, first, last in blocks]
    tags = None
    if kickoff_tags:
        starts = kickoff_tag_starts(load_smart_tagging.load())
        tags = [starts.get(half) for half, _, _ in blocks]
    kwargs = {} if params is None else {"params": params}
    return possession.label_match(tracking, halves, games.source_frames("tactical"),
                                  report=report, kickoff_tags=tags, **kwargs)


def write(labels, path):
    baseline.write_submission(path, np.array(pm.LABELS)[labels])
    reason = pm.validate_submission(pm.read_label_csv(path), games.source_frames("tactical"))
    return reason, hashlib.sha256(open(path, "rb").read()).hexdigest()


def sustained_play_from(labels, first):
    alive = np.isin(labels, (pm.H, pm.A)).astype(np.int64)
    total = np.concatenate(([0], np.cumsum(alive)))
    for f in range(first, len(labels) - SUSTAINED_PLAY_FRAMES):
        if total[f + SUSTAINED_PLAY_FRAMES] - total[f] == SUSTAINED_PLAY_FRAMES:
            return f
    return len(labels)


def checks(labels):
    """Aggregate correctness checks against facts the organisers publish (DATA.md, FAQ.md)."""
    runs = pm.valid_runs(np.where(labels == pm.X, pm.X, 0).astype(np.int8))
    segments = pm.segments(labels, runs)
    spells = [b - a for a, b, k in segments if k in (pm.H, pm.A)]
    (_, first1, _), (_, first2, _) = games.half_video_blocks(games.GAME)
    pre = labels[first2:PUBLISHED_SECOND_HALF_KICKOFF]
    play1 = (sustained_play_from(labels, first1) - first1) / 25.0
    play2 = (sustained_play_from(labels, first2) - PUBLISHED_SECOND_HALF_KICKOFF) / 25.0
    ok = (np.mean(pre == pm.D) >= PRE_KICKOFF_DEAD_SHARE
          and abs(play2) * 25 <= TOLERANCE_FRAMES and play1 * 25 <= TOLERANCE_FRAMES)
    return {"possessions": len(spells), "mean_s": np.mean(spells) / 25.0,
            "stoppages": sum(1 for _, _, k in segments if k == pm.D),
            "pre_dead": 100.0 * np.mean(pre == pm.D), "play1": play1, "play2": play2, "ok": ok}


def opening_breakdown(labels, entry, ball, first, last, kickoff):
    """Where a half's opening goes wrong, as aggregates, measured from a published kickoff that is
    only the reference point, as in checks(); nothing here feeds the labelling."""
    kick = entry["opening_kick"]
    alive = np.flatnonzero(np.isin(labels[first:last + 1], (pm.H, pm.A)))
    live = first + int(alive[0]) if len(alive) else last + 1
    after = labels[kick:kick + SUSTAINED_PLAY_FRAMES]
    return {
        "kick_s": (kick - kickoff) / 25.0,
        "live_s": (live - kickoff) / 25.0,
        "opening_made_by": entry["stoppages"][0][2],
        "dead_after_kick_s": np.sum(after == pm.D) / 25.0,
        "stoppages_after_kick": [k for b0, _, k in entry["stoppages"]
                                 if kick < b0 <= kick + SUSTAINED_PLAY_FRAMES],
        "ball_seen_to_kick": (100.0 * np.mean(~np.isnan(ball[kickoff:kick, 0]))
                              if kick > kickoff else None),
    }


def print_breakdown(b):
    print("  2nd-half opening diagnostic (published kickoff as reference only):")
    print("    opening kick {:+.1f} s   first live frame {:+.1f} s   from the published "
          "kickoff".format(b["kick_s"], b["live_s"]))
    print("    opening dead stretch made by: {}".format(b["opening_made_by"]))
    print("    in the 10 s after the opening kick: {:.1f} s dead, stoppages starting: {}".format(
        b["dead_after_kick_s"], ", ".join(b["stoppages_after_kick"]) or "none"))
    print("    ball seen from the published kickoff to the opening kick: {}".format(
        "n/a (kick not late)" if b["ball_seen_to_kick"] is None
        else "{:.0f}%".format(b["ball_seen_to_kick"])))


def describe(name, labels, gt):
    c = checks(labels)
    r = pm.evaluate(gt, labels, bootstrap_n=1000)
    print("{}".format(name))
    print("  possessions {}  mean {:.1f} s  stoppages {}".format(
        c["possessions"], c["mean_s"], c["stoppages"]))
    print("  1st half: sustained play starts {:+.0f} s after its first graded frame".format(
        c["play1"]))
    print("  2nd half: pre-kickoff stretch labelled dead {:.0f}%   sustained play starts {:+.0f} s "
          "from the published kickoff".format(c["pre_dead"], c["play2"]))
    print("  half-opening checks: {}".format("PASS" if c["ok"] else "FAIL"))
    print("  public 5 min (correctness check only): spellF1 {:.3f} [{:.3f}-{:.3f}]  macroF1 {:.3f}"
          "  poss {} (truth {})".format(r["spell_f1_mean"], r["spell_bootstrap_low"],
                                        r["spell_bootstrap_high"], r["macro_f1"],
                                        r["n_pred_spells"], r["n_gt_spells"]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    gt = pm.label_codes(pm.read_label_csv(PUBLIC_GT))
    tracking = epts.load_match("tactical")
    report = []
    labels = build(tracking, report=report)
    reason, digest = write(labels, args.out)
    print("validator  {}".format("OK" if reason is None else "FAIL: " + reason))
    describe("written file (half opens on first kick at or after its Smart Tagging kickoff window, "
             "followed by 10 s of play): {} / {}".format(*[r["branch"] for r in report]),
             labels, gt)
    _, (_, first2, last2) = games.half_video_blocks(games.GAME)
    print_breakdown(opening_breakdown(labels, report[1],
                                      evidence.clean_ball(tracking.ball_xy, DEFAULT),
                                      first2, last2, PUBLISHED_SECOND_HALF_KICKOFF))
    describe("comparison, not written (no Smart Tagging, as in aa57441)",
             build(tracking, kickoff_tags=False), gt)
    describe("comparison, not written (Smart Tagging, then plain first kick)",
             build(tracking, params=dataclasses.replace(DEFAULT, opening_play_frames=0)), gt)
    print("sha256  {}".format(digest))
