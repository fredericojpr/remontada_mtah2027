"""One test per possession rule, on small hand-built scenes (metres, 25 fps)."""

import dataclasses
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
    n = 600
    ball = np.column_stack([np.full(n, 50.0), np.full(n, 30.0)])
    ball[300:350] = [50.0, 68.8]
    ball[350:] = np.column_stack([50 + 0.2 * np.arange(n - 350), np.full(n - 350, 30.0)])
    ball = with_kickoff(ball)
    speed = evidence.ball_speed(ball)
    stops = dead_ball.stoppages(ball, speed, np.full(n, 3.0), PITCH, 0, n - 1, P)
    assert stops[-1] == (300, 350)


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
    n = 700
    ball = np.tile([50.0, 30.0], (n, 1))
    ball[400:] = np.column_stack([np.linspace(50, 90, n - 400), np.full(n - 400, 30.0)])
    ball = with_kickoff(ball)
    median = np.full(n, 3.0)
    median[300:380] = 0.8
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, n - 1, P)
    assert stops[-1] == (300, 401)


def test_rule8_short_stoppages_are_dropped():
    n = 700
    ball = with_kickoff(np.tile([50.0, 30.0], (n, 1)))
    ball[400:410] = [50.0, 68.8]
    ball[410:] = np.column_stack([50 + 0.2 * np.arange(n - 410), np.full(n - 410, 30.0)])
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), np.full(n, 3.0), PITCH, 0, n - 1, P)
    assert stops[0][1] < 20 and not any(begin == 400 for begin, _ in stops)


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


def test_rule10_taps_followed_by_standing_still_do_not_open_the_half():
    n = 1500
    ball = np.tile([52.5, 34.0], (n, 1))
    ball[100:120] = np.column_stack([np.linspace(52.5, 47.5, 20), np.full(20, 34.0)])
    ball[120:900] = [47.5, 34.0]
    ball[900:] = np.column_stack([47.5 + 0.2 * np.arange(n - 900), np.full(n - 900, 34.0)])
    median = np.full(n, 0.5)
    median[900:] = 3.0
    report = []
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, n - 1, P,
                                report)
    assert stops[0][0] == 0 and stops[0][1] in (900, 901, 902)
    assert [r["branch"] for r in report] == ["first kick followed by play"]


def test_rule10_opening_is_the_first_kick_followed_by_play_and_zero_window_is_first_kick():
    kicks = np.array([100, 900])
    assert dead_ball.opening_restart(kicks, [130], 2000, P) == (900, "first kick followed by play")
    zero = dataclasses.replace(P, opening_play_frames=0)
    assert dead_ball.opening_restart(kicks, [130], 2000, zero)[0] == 100
    assert dead_ball.opening_restart(kicks, [130, 950], 2000, P) == (100, "first kick")


def tag(code, kind, half, start_frame):
    return {"code": code, "start_frame": start_frame, "tags": {"Type": kind, "Half": half}}


def test_rule10_kickoff_tag_starts_reads_only_start_of_half_kickoffs():
    events = [tag("SET PIECES", "Kick Off (Start)", "1st Half", 100),
              tag("set pieces", "kick off (start)", "2nd Half", 900),
              tag("SET PIECES", "Kick Off (After Goal)", "2nd Half", 500),
              tag("SET PIECES", "Throw-in", "2nd Half", 400),
              tag("BUILD UP", "Kick Off (Start)", "2nd Half", 300)]
    assert dead_ball.kickoff_tag_starts(events) == {1: 100, 2: 900}
    assert dead_ball.kickoff_tag_starts(events[2:]) == {}


def pre_kickoff_play(n=1500):
    """Play-like movement from the half's first frame, then the ball at the centre mark until a
    kickoff at 600; players never stand still, so no stoppage rule fires before it."""
    ball = np.tile([52.5, 34.0], (n, 1))
    ball[50:200] = np.column_stack([np.linspace(40.0, 52.5, 150), np.full(150, 34.0)])
    ball[600:] = np.column_stack([52.5 + 0.2 * np.arange(n - 600), np.full(n - 600, 34.0)])
    return ball, np.full(n, 3.0)


def test_rule10_kicks_before_the_kickoff_tag_do_not_open_the_half():
    ball, median = pre_kickoff_play()
    speed = evidence.ball_speed(ball)
    untagged = dead_ball.stoppages(ball, speed, median, PITCH, 0, len(ball) - 1, P)
    assert untagged[0][1] < 100
    report = []
    stops = dead_ball.stoppages(ball, speed, median, PITCH, 0, len(ball) - 1, P, report, 590)
    assert stops[0][0] == 0 and stops[0][1] in (600, 601, 602)
    assert report[0]["branch"] == "kickoff tag, first kick followed by play"
    assert report[0]["opening_kick"] in (600, 601, 602)


def test_rule10_kickoff_tag_before_the_half_changes_nothing():
    ball, median = pre_kickoff_play()
    speed = evidence.ball_speed(ball)
    stops = dead_ball.stoppages(ball, speed, median, PITCH, 100, len(ball) - 1, P)
    assert dead_ball.stoppages(ball, speed, median, PITCH, 100, len(ball) - 1, P, None, 10) == stops


def test_rule10_without_a_kick_after_the_tag_falls_back_to_the_kicks():
    ball, median = pre_kickoff_play()
    speed = evidence.ball_speed(ball)
    report = []
    untagged = dead_ball.stoppages(ball, speed, median, PITCH, 0, len(ball) - 1, P)
    stops = dead_ball.stoppages(ball, speed, median, PITCH, 0, len(ball) - 1, P, report, 1490)
    assert stops == untagged and report[0]["branch"].startswith("no kick after kickoff tag, ")


def test_rule10_label_match_keeps_the_pre_kickoff_stretch_dead_with_a_tag():
    ball, _ = pre_kickoff_play()
    tracking = scene(len(ball), ball, [52.5, 34.5], [60.0, 34.0])
    tracking.ball_xy = ball
    text = string(possession.label_match(tracking, [(0, len(ball) - 1)], len(ball),
                                         kickoff_tags=[590]))
    assert set(text[:600]) == {"D"} and "D" not in text[603:850]


def test_rule10_report_names_a_halt_merged_into_the_opening():
    ball, median = pre_kickoff_play()
    ball[600:620] = np.column_stack([np.linspace(52.5, 56.5, 20), np.full(20, 34.0)])
    ball[620:800] = [56.5, 34.0]
    ball[800:] = np.column_stack([56.5 + 0.2 * np.arange(len(ball) - 800),
                                  np.full(len(ball) - 800, 34.0)])
    median[620:800] = 0.5
    zero = dataclasses.replace(P, opening_play_frames=0)
    report = []
    stops = dead_ball.stoppages(ball, evidence.ball_speed(ball), median, PITCH, 0, len(ball) - 1,
                                zero, report, 590)
    assert report[0]["opening_kick"] in (600, 601, 602)
    assert report[0]["stoppages"][0][2] == "kickoff+halt" and stops[0][1] in (800, 801, 802)
