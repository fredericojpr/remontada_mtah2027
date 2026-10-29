"""Rules 4, 5 and 10: the state machine that turns stoppages and gains into H/A/D/X labels."""

import numpy as np

from team_a import dead_ball, evidence
from team_a.config import DEFAULT

H, A, D, X = 0, 1, 2, 3


def label_half(labels, first, last, stops, gain_events, nearest, params):
    """Fill labels[first:last + 1]. Possession changes only on a gain by the other team (rule 4)."""
    timeline = []
    for begin, restart in stops:
        timeline.append((begin, 0, "stop", None))
        team = dead_ball.restart_team(nearest, restart, params)
        if team == evidence.NONE:
            team = next((t for f, t in gain_events if f >= restart), None)
        timeline.append((restart, 1, "restart", team))
    timeline += [(f, 2, "gain", t) for f, t in gain_events if first <= f <= last]

    state, since, alive, previous = D, first, False, H
    for frame, _, kind, team in sorted(timeline, key=lambda e: (e[0], e[1])):
        frame = min(max(frame, since), last + 1)
        if kind == "stop":
            labels[since:frame] = state
            if state in (H, A):
                previous = state
            state, since, alive = D, frame, False
        elif kind == "restart":
            labels[since:frame] = state
            state = previous if team is None else team
            since, alive = frame, True
        elif alive and team != state:
            labels[since:frame] = state
            state, since = team, frame
    labels[since:last + 1] = state


def label_match(tracking, halves, n_frames, params=DEFAULT, report=None):
    """H/A/D per graded frame, X elsewhere. halves: [(first, last)] video frames, inclusive."""
    if not np.array_equal(tracking.frame_id, np.arange(1, len(tracking.frame_id) + 1)):
        raise ValueError("tracking must hold one record per video frame, frame_id 1..N")
    ball = evidence.clean_ball(tracking.ball_xy, params)
    speed = evidence.ball_speed(ball)
    missing = np.isnan(ball[:, 0])
    controlled = evidence.control(tracking, ball, params)
    gain_events = evidence.gains(controlled, missing, params)
    median_speed = dead_ball.median_player_speed(tracking.slot_speed)

    home, away = evidence.nearest_distance_per_team(tracking, ball)
    nearest = np.where(np.isinf(np.minimum(home, away)), evidence.NONE,
                       np.where(home <= away, H, A)).astype(np.int8)

    labels = np.full(n_frames, X, dtype=np.int8)
    for first, last in halves:
        stops = dead_ball.stoppages(ball, speed, median_speed, tracking.pitch, first, last, params,
                                    report)
        inside = [(f, t) for f, t in gain_events if first <= f <= last]
        label_half(labels, first, last, stops, inside, nearest, params)
    return labels
