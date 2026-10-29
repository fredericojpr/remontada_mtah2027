import hashlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from team_a import epts, pipeline, possession  # noqa: E402
from tests import synth  # noqa: E402

PITCH = (105.3, 68.0)


def test_labels_are_deterministic_and_graded_only_inside_halves(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=2000, seed=3)
    tracking = epts.load(meta, raw, PITCH)
    halves = [(100, 899), (1100, 1899)]
    first = possession.label_match(tracking, halves, 2000)
    second = possession.label_match(tracking, halves, 2000)
    assert hashlib.sha256(first.tobytes()).hexdigest() == hashlib.sha256(second.tobytes()).hexdigest()
    graded = np.zeros(2000, dtype=bool)
    for a, b in halves:
        graded[a:b + 1] = True
    assert (first[~graded] == possession.X).all()
    assert not (first[graded] == possession.X).any()


def test_opening_breakdown_splits_a_late_kick_from_dead_time_after_it():
    labels = np.full(1000, possession.H, dtype=np.int8)
    labels[:175] = possession.D
    labels[300:360] = possession.D
    ball = np.zeros((1000, 2))
    ball[100:150] = np.nan
    entry = {"opening_kick": 175, "stoppages": [(0, 175, "kickoff"), (300, 360, "halt")]}
    b = pipeline.opening_breakdown(labels, entry, ball, 0, 999, 100)
    assert (b["kick_s"], b["live_s"], b["opening_made_by"]) == (3.0, 3.0, "kickoff")
    assert b["dead_after_kick_s"] == 2.4 and b["stoppages_after_kick"] == ["halt"]
    assert round(b["ball_seen_to_kick"], 1) == 33.3
    entry["opening_kick"] = 90
    assert pipeline.opening_breakdown(labels, entry, ball, 0, 999, 100)["ball_seen_to_kick"] is None
