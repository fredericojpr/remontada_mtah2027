"""One test per possession rule, on small hand-built scenes (metres, 25 fps)."""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from team_a import dead_ball, epts, evidence, possession  # noqa: E402
from team_a.config import DEFAULT as P  # noqa: E402

PITCH = (105.0, 68.0)
H, A, D, X = possession.H, possession.A, possession.D, possession.X


def scene(n, ball, home_xy, away_xy, speed=3.0):
    """One home and one away player; ball/players as (n, 2) arrays or fixed points."""
    slots = np.stack([np.broadcast_to(home_xy, (n, 2)), np.broadcast_to(away_xy, (n, 2))], axis=1)
    return epts.Tracking(np.arange(1, n + 1), np.broadcast_to(ball, (n, 2)).astype(float).copy(),
                         slots.astype(float).copy(), np.full((n, 2), float(speed)),
                         np.tile(np.array([0, 1], dtype=np.int8), (n, 1)), PITCH)


def with_kickoff(ball):
    ball[:10] = np.column_stack([np.linspace(40.0, 50.0, 10), np.full(10, ball[10, 1])])
    return ball


def string(labels):
    return "".join("HADX"[c] for c in labels)


def test_rule1_fills_short_gaps_only_and_never_smooths_across_a_gap():
    ball = np.column_stack([np.arange(40.0), np.zeros(40)])
    ball[5:10] = np.nan
    ball[20:32] = np.nan
    clean = evidence.clean_ball(ball, P)
    np.testing.assert_allclose(clean[5:10, 0], np.arange(5.0, 10.0))
    assert np.isnan(clean[20:32]).all()
    assert clean[19, 0] == np.mean([17.0, 18.0, 19.0])


def test_rule2_control_needs_radius_and_margin():
    tracking = scene(3, [50.0, 30.0], [51.0, 30.0], [51.4, 30.0])
    assert evidence.control(tracking, tracking.ball_xy, P).tolist() == [-1, -1, -1]
    tracking = scene(3, [50.0, 30.0], [51.0, 30.0], [52.0, 30.0])
    assert evidence.control(tracking, tracking.ball_xy, P).tolist() == [H, H, H]
    tracking = scene(3, [50.0, 30.0], [52.0, 30.0], [60.0, 30.0])
    assert evidence.control(tracking, tracking.ball_xy, P).tolist() == [-1, -1, -1]


def test_rule3_gain_needs_eight_frames_bridges_short_dropouts_and_is_backdated():
    controlled = np.full(40, -1, dtype=np.int8)
    controlled[2:9] = A
    controlled[20:24] = A
    controlled[26:30] = A
    missing = np.zeros(40, dtype=bool)
    assert evidence.gains(controlled, missing, P) == [(20, A)]


def test_rule4_short_touches_do_not_change_possession():
    labels = np.full(100, X, dtype=np.int8)
    stops = [(0, 0)]
    possession.label_half(labels, 0, 99, stops, [(0, H), (50, A), (52, H)][:1], np.full(100, H), P)
    assert string(labels) == "H" * 100
    labels[:] = X
    possession.label_half(labels, 0, 99, stops, [(0, H), (60, A)], np.full(100, H), P)
    assert string(labels) == "H" * 60 + "A" * 40


def test_rule5_switch_after_a_ball_gap_is_backdated_to_mid_gap():
    controlled = np.full(200, -1, dtype=np.int8)
    controlled[100:120] = A
    missing = np.zeros(200, dtype=bool)
    missing[60:100] = True
    assert evidence.gains(controlled, missing, P) == [(80, A)]
    missing[:100] = True
    assert evidence.gains(controlled, missing, P) == [(100 - P.gap_backdate_max_frames, A)]


def test_rule6_ball_beyond_a_line_stops_play():
    n = 300
    ball = np.column_stack([np.full(n, 50.0), np.full(n, 30.0)])
    ball[100:150] = [50.0, 68.8]
    ball[150:] = np.column_stack([np.linspace(50, 80, n - 150), np.full(n - 150, 30.0)])
    ball = with_kickoff(ball)
    speed = evidence.ball_speed(ball)
    stops = dead_ball.stoppages(ball, speed, np.full(n, 3.0), PITCH, 0, n - 1, P)
    assert stops[-1] == (100, 150)


def test_rule7_collective_halt_stops_play_only_after_three_seconds():
    n = 400
    ball = with_kickoff(np.tile([50.0, 30.0], (n, 1)))
    median = np.full(n, 3.0)
    median[100:300] = 0.8
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, n - 1, P)
    assert any(begin == 100 for begin, _ in stops)
    median[100:300] = 3.0
    median[100:170] = 0.8
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, n - 1, P)
    assert not any(begin == 100 for begin, _ in stops)


def test_rule8_restart_is_the_first_kick_after_a_stoppage():
    n = 500
    ball = np.tile([50.0, 30.0], (n, 1))
    ball[200:] = np.column_stack([np.linspace(50, 90, n - 200), np.full(n - 200, 30.0)])
    ball = with_kickoff(ball)
    median = np.full(n, 3.0)
    median[100:180] = 0.8
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, n - 1, P)
    assert stops[-1] == (100, 201)


def test_rule8_short_stoppages_are_dropped():
    n = 400
    ball = with_kickoff(np.tile([50.0, 30.0], (n, 1)))
    ball[200:210] = [50.0, 68.8]
    ball[210:] = np.column_stack([50 + 0.2 * np.arange(n - 210), np.full(n - 210, 30.0)])
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), np.full(n, 3.0), PITCH, 0, n - 1, P)
    assert not any(begin == 200 for begin, _ in stops)


def test_rule9_restart_team_is_the_taker():
    nearest = np.full(100, H, dtype=np.int8)
    nearest[60:80] = A
    assert dead_ball.restart_team(nearest, 80, P) == A
    assert dead_ball.restart_team(np.full(100, -1, dtype=np.int8), 80, P) == -1


def test_rule10_half_starts_dead_until_kickoff_and_only_halves_are_graded():
    n = 400
    ball = np.column_stack([np.full(n, 52.5), np.full(n, 34.0)])
    ball[150:] = np.column_stack([52.5 + 0.2 * np.arange(n - 150), np.full(n - 150, 34.0)])
    tracking = scene(n, ball, [52.5, 34.5], [60.0, 34.0])
    tracking.ball_xy = ball
    labels = possession.label_match(tracking, [(100, 349)], n)
    text = string(labels)
    assert text[:100] == "X" * 100 and text[350:] == "X" * 50
    assert set(text[100:151]) == {"D"} and "X" not in text[100:350]
    assert text.index("H") in (151, 152)


def teams_scene(n, ball, home_x, away_x):
    """Seven players per team standing at the given x positions (per frame), spread across y."""
    y = np.linspace(10.0, 58.0, 7)
    home = np.stack([np.column_stack([home_x, np.full(n, yy)]) for yy in y], axis=1)
    away = np.stack([np.column_stack([away_x, np.full(n, yy)]) for yy in y], axis=1)
    home[:, 3] = [52.0, 34.0]
    slots = np.concatenate([home, away], axis=1)
    team = np.tile(np.array([0] * 7 + [1] * 7, dtype=np.int8), (n, 1))
    return epts.Tracking(np.arange(1, n + 1), ball, slots, np.full((n, 14), 3.0), team, PITCH)


def test_rule10_only_a_kick_from_the_kickoff_formation_starts_the_half():
    n = 400
    ball = np.column_stack([np.full(n, 52.5), np.full(n, 34.0)])
    ball[100:120] = np.column_stack([np.linspace(52.5, 62.5, 20), np.full(20, 34.0)])
    ball[120:200] = [52.5, 34.0]
    ball[200:] = np.column_stack([52.5 - 0.2 * np.arange(n - 200), np.full(n - 200, 34.0)])
    t = np.arange(n)
    home_x = np.where(t < 150, 60.0, np.where(t < 230, 30.0, 60.0))
    tracking = teams_scene(n, ball, home_x, np.full(n, 75.0))
    report = []
    text = string(possession.label_match(tracking, [(90, 349)], n, report=report))
    assert set(text[90:201]) == {"D"}
    assert text.index("H") in (201, 202)
    assert report == ["kick as formation broke"]


def test_rule10_kickoff_on_the_first_graded_frame_with_formation_from_before_grading():
    n = 600
    t = np.arange(n)
    ball = np.column_stack([np.full(n, 52.5), np.full(n, 34.0)])
    ball[300:] = np.column_stack([52.5 - 0.2 * np.arange(n - 300), np.full(n - 300, 34.0)])
    home_x = np.where(t < 350, 30.0, 60.0)
    tracking = teams_scene(n, ball, home_x, np.full(n, 75.0))
    report = []
    text = string(possession.label_match(tracking, [(300, 599)], n, report=report))
    assert text.index("H") in (300, 301, 302)
    assert report == ["kick as formation broke"]


def test_rule10_early_tap_with_the_ball_unseen_at_the_real_kickoff():
    n = 1600
    t = np.arange(n)
    ball = np.column_stack([np.full(n, 52.5), np.full(n, 34.0)])
    ball[200:220] = np.column_stack([np.linspace(52.5, 50.0, 20), np.full(20, 34.0)])
    ball[220:1100] = [52.5, 34.0]
    ball[1100:1180] = np.nan
    ball[1180:] = np.column_stack([40.0 - 0.2 * np.arange(n - 1180), np.full(n - 1180, 34.0)])
    home_x = np.where(t < 100, 60.0, np.where(t < 1110, 30.0, 60.0))
    tracking = teams_scene(n, ball, home_x, np.full(n, 75.0))
    report = []
    text = string(possession.label_match(tracking, [(50, 1599)], n, report=report))
    assert report == ["formation broke"]
    assert set(text[50:1110]) == {"D"}
