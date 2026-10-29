"""Rules 1-3, plus the backdating of rule 5: clean the ball, find who controls it, find gains."""

import numpy as np

from team_a.config import FPS

NONE = -1


def runs(mask):
    """[(start, stop)] half-open spans where mask is True."""
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def bridge(mask, max_gap):
    out = mask.copy()
    for start, stop in runs(~mask):
        if 0 < start and stop < len(mask) and stop - start <= max_gap:
            out[start:stop] = True
    return out


def clean_ball(ball_xy, params):
    """Rule 1: fill short gaps linearly, then smooth inside visible stretches only."""
    ball = ball_xy.copy()
    missing = np.isnan(ball[:, 0])
    for start, stop in runs(missing):
        if 0 < start and stop < len(ball) and stop - start <= params.ball_gap_fill_frames:
            weight = (np.arange(start, stop) - (start - 1))[:, None] / (stop - start + 1)
            ball[start:stop] = ball[start - 1] + weight * (ball[stop] - ball[start - 1])
    half = params.ball_smooth_frames // 2
    smoothed = ball.copy()
    for start, stop in runs(~np.isnan(ball[:, 0])):
        segment = ball[start:stop]
        total = np.vstack([np.zeros((1, 2)), np.cumsum(segment, axis=0)])
        index = np.arange(stop - start)
        low, high = np.maximum(0, index - half), np.minimum(stop - start, index + half + 1)
        smoothed[start:stop] = (total[high] - total[low]) / (high - low)[:, None]
    return smoothed


def ball_speed(ball):
    speed = np.full(len(ball), np.nan)
    speed[1:] = np.hypot(*(ball[1:] - ball[:-1]).T) * FPS
    return speed


def nearest_distance_per_team(tracking, ball):
    distance = np.hypot(*(tracking.slot_xy - ball[:, None, :]).transpose(2, 0, 1))
    distance = np.where(np.isnan(distance), np.inf, distance)
    return [np.where(tracking.slot_team == team, distance, np.inf).min(axis=1) for team in (0, 1)]


def control(tracking, ball, params):
    """Rule 2: a team controls the ball when its nearest player is within the radius and clearly
    closer than any opponent."""
    home, away = nearest_distance_per_team(tracking, ball)
    out = np.full(len(ball), NONE, dtype=np.int8)
    out[(home <= params.control_radius_m) & (home + params.control_margin_m <= away)] = 0
    out[(away <= params.control_radius_m) & (away + params.control_margin_m <= home)] = 1
    out[np.isnan(ball[:, 0])] = NONE
    return out


def gains(controlled, ball_missing, params):
    """Rule 3: [(switch_frame, team)] for every spell of control long enough to count.

    The switch is the first controlled frame, or mid-gap when the spell begins right after a
    ball gap (rule 5).
    """
    events = []
    for team in (0, 1):
        held = bridge(controlled == team, params.gain_dropout_frames)
        for start, stop in runs(held):
            if stop - start < params.gain_frames:
                continue
            switch = start
            if start > 0 and ball_missing[start - 1]:
                gap_start = start - 1
                while gap_start > 0 and ball_missing[gap_start - 1]:
                    gap_start -= 1
                switch = start - min((start - gap_start) // 2, params.gap_backdate_max_frames)
            events.append((switch, team))
    return sorted(events)
