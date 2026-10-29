import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "starter"))

import baseline  # noqa: E402
from team_a import epts  # noqa: E402
from tests import synth  # noqa: E402

PITCH = (105.3, 68.0)


def test_parse_shapes_and_units(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=50)
    tracking = epts.load(meta, raw, PITCH)
    assert tracking.frame_id.tolist() == list(range(1, 51))
    assert tracking.slot_xy.shape == (50, synth.N_SLOTS, 2)
    assert tracking.slot_team.shape == (50, synth.N_SLOTS)
    assert tracking.slot_team[0].tolist() == [0, 0, 0, 1, 1, 1]
    assert np.nanmax(tracking.slot_xy[:, :, 0]) <= PITCH[0]
    assert np.isnan(tracking.slot_xy[7]).all()


def test_cache_roundtrip(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=30)
    cache = os.path.join(str(tmp_path), "cache", "x.npz")
    first = epts.load(meta, raw, PITCH, cache)
    second = epts.load(meta, raw, PITCH, cache)
    assert os.path.isfile(cache)
    np.testing.assert_array_equal(first.slot_xy, second.slot_xy)
    np.testing.assert_array_equal(first.ball_xy, second.ball_xy)


def test_nearest_team_matches_organisers_baseline(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=500)
    tracking = epts.load(meta, raw, PITCH)
    ours = epts.nearest_team(tracking)
    theirs = baseline.nearest_player_labels(raw, baseline.team_of_each_track(meta), 500, PITCH)
    np.testing.assert_array_equal(ours, theirs)


def test_doctor_serialisation_matches_write_submission(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=300)
    labels = baseline.smooth(epts.nearest_team(epts.load(meta, raw, PITCH)), 0)
    path = baseline.write_submission(os.path.join(str(tmp_path), "b.csv"), labels)
    ours = "frame,label\n" + "".join("{},{}\n".format(i, l) for i, l in enumerate(labels))
    assert open(path).read() == ours
