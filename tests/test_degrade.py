import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from team_a import degrade, epts  # noqa: E402
from tests import synth  # noqa: E402

PITCH = (105.0, 68.0)


def clean_match(tmp_path, n_frames=2000):
    meta, raw = synth.write_match(str(tmp_path), n_frames=n_frames)
    tracking = epts.load(meta, raw, PITCH)
    tracking.ball_xy = np.nan_to_num(tracking.ball_xy, nan=50.0)
    tracking.slot_xy = np.nan_to_num(tracking.slot_xy, nan=30.0)
    return tracking


def test_our_ball_missing_rate_matches_published_figure():
    assert 0.40 < degrade.our_ball_missing().mean() < 0.42


def test_degrade_is_deterministic_and_keeps_shapes(tmp_path):
    tracking = clean_match(tmp_path)
    first, second = degrade.degrade(tracking), degrade.degrade(tracking)
    np.testing.assert_array_equal(first.ball_xy, second.ball_xy)
    np.testing.assert_array_equal(first.slot_xy, second.slot_xy)
    assert first.slot_xy.shape == tracking.slot_xy.shape


def test_degrade_applies_gaps_dropouts_and_noise(tmp_path):
    tracking = clean_match(tmp_path)
    out = degrade.degrade(tracking)
    expected = np.resize(degrade.our_ball_missing(), len(tracking.frame_id))
    np.testing.assert_array_equal(np.isnan(out.ball_xy[:, 0]), expected)
    assert 0.03 < np.isnan(out.slot_xy[:, :, 0]).mean() < 0.12
    seen = ~np.isnan(out.slot_xy)
    assert 0.1 < np.std(out.slot_xy[seen] - tracking.slot_xy[seen]) < 0.3


def test_speeds_from_positions_constant_motion():
    xy = np.zeros((20, 1, 2))
    xy[:, 0, 0] = np.arange(20) * 0.2
    speed = epts.speeds_from_positions(xy)
    np.testing.assert_allclose(speed[3:-3, 0], 5.0)
