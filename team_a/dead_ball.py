"""Rules 6-9: when the ball goes dead, when play restarts, and who restarts it."""

import warnings

import numpy as np

from team_a.config import FPS
from team_a.evidence import NONE, bridge, runs


def median_player_speed(slot_speed):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(slot_speed, axis=1)


def beyond_lines(ball, pitch, margin):
    length, width = pitch
    x, y = ball[:, 0], ball[:, 1]
    with np.errstate(invalid="ignore"):
        return (x < -margin) | (x > length + margin) | (y < -margin) | (y > width + margin)


def travels(ball, pitch, params):
    """Frames from which the in-bounds ball covers the kick distance within the kick window."""
    k = params.kick_window_frames
    out = np.zeros(len(ball), dtype=bool)
    if len(ball) <= k:
        return out
    start, end = ball[:-k], ball[k:]
    with np.errstate(invalid="ignore"):
        far = np.hypot(*(end - start).T) >= params.kick_distance_m
    inside = ~beyond_lines(start, pitch, 0.0) & ~np.isnan(start[:, 0]) & ~np.isnan(end[:, 0])
    out[:-k] = far & inside
    return out


def kick_frames(travelling, speed, params):
    """The frame the ball is struck: inside each travel window, the first frame faster than the
    window's average kick speed."""
    threshold = params.kick_distance_m * FPS / params.kick_window_frames
    out = []
    for start, stop in runs(travelling):
        window = speed[start:min(stop, start + params.kick_window_frames + 1)]
        with np.errstate(invalid="ignore"):
            fast = np.flatnonzero(window > threshold)
        out.append(start + int(fast[0]) if len(fast) else start)
    return out


def run_starts(mask, min_frames):
    return [start for start, stop in runs(mask) if stop - start >= min_frames]


def kickoff_formation(tracking, params):
    """Frames where each team stands in its own half, as at a kickoff (rule 10)."""
    x = tracking.slot_xy[:, :, 0] - tracking.pitch[0] / 2.0
    seen = ~np.isnan(x)
    home, away = seen & (tracking.slot_team == 0), seen & (tracking.slot_team == 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        home_side = np.sign(np.nanmedian(np.where(home, x, np.nan), axis=1))
    with np.errstate(invalid="ignore"):
        side = np.sign(x)
    n_home, n_away = home.sum(axis=1), away.sum(axis=1)
    own_home = (home & (side == home_side[:, None])).sum(axis=1)
    own_away = (away & (side == -home_side[:, None])).sum(axis=1)
    share = params.kickoff_own_half_share
    return ((n_home >= params.kickoff_min_players) & (n_away >= params.kickoff_min_players)
            & (own_home >= share * n_home) & (own_away >= share * n_away) & (home_side != 0))


def opening_restart(kicks, formation, first, n, params):
    """(restart, branch) relative to the half's first frame.

    The kickoff formation is the first one held for at least 2 s (1 s flickers bridged) that is
    still standing at the half's start or forms after it. The kickoff is the last kick shortly
    before it breaks up; with no such kick seen, the moment it breaks; failing both, the first
    kick of the half.
    """
    held = bridge(formation, params.taker_window_frames)
    for start, stop in runs(held):
        if stop - start < params.kickoff_formation_min_frames or stop <= first:
            continue
        end = stop - first
        near = kicks[(kicks >= end - params.kickoff_break_frames)
                     & (kicks <= end + params.taker_window_frames)]
        if len(near):
            return int(near[-1]), "kick as formation broke"
        return end, "formation broke"
    if len(kicks):
        return int(kicks[0]), "first kick"
    return n, "no kickoff found"


def stoppages(ball, speed, median_speed, pitch, first, last, params, formation=None,
              report=None):
    """[(dead_from, restart_at)] inside one graded half, frames [first, last].

    Rule 6: ball out. Rule 7: collective halt. Rule 8: restart on a kick, or when players move
    again with the ball unseen after a halt. Each half starts dead until its kickoff (rule 10).
    """
    stop = last + 1
    window = slice(first, stop)
    b, s, m = ball[window], speed[window], median_speed[window]
    missing = np.isnan(b[:, 0])
    with np.errstate(invalid="ignore"):
        slow = m < params.halt_speed_mps
        moving = m > params.halt_speed_mps
        still_ball = missing | (s < params.still_ball_mps)
        kicked = travels(b, pitch, params)

    starts = sorted([(f, "out") for f in run_starts(
        beyond_lines(b, pitch, params.out_margin_m), params.out_frames)]
        + [(f, "halt") for f in run_starts(slow & still_ball, params.halt_frames)])
    kicks = np.array(kick_frames(kicked, s, params), dtype=np.int64)
    resumes = np.array(run_starts(missing & moving, params.resume_frames), dtype=np.int64)
    if formation is None:
        formation = np.zeros(len(ball), dtype=bool)
    opening, branch = opening_restart(kicks, formation, first, stop - first, params)
    if report is not None:
        report.append(branch)

    found, t = [], 0
    for begin, kind in [(0, "kickoff")] + starts:
        if begin < t:
            continue
        if kind == "kickoff":
            restart = opening
        else:
            options = [kicks[kicks >= begin][:1]]
            if kind == "halt":
                options.append(resumes[resumes >= begin][:1])
            options = np.concatenate(options)
            restart = int(options.min()) if len(options) else stop - first
        found.append([begin, restart])
        t = restart

    merged = []
    for begin, restart in found:
        if merged and begin - merged[-1][1] < params.min_play_frames:
            merged[-1][1] = restart
        else:
            merged.append([begin, restart])
    kept = [(b0, r0) for i, (b0, r0) in enumerate(merged)
            if i == 0 or r0 - b0 >= params.min_stoppage_frames]
    return [(first + b0, first + r0) for b0, r0 in kept]


def restart_team(nearest, restart, params):
    """Rule 9: the team nearest the ball in the last second before the restart, or NONE."""
    window = nearest[max(0, restart - params.taker_window_frames):restart + 1]
    seen = window[window >= 0]
    if not len(seen):
        return NONE
    home = int(np.sum(seen == 0))
    away = int(np.sum(seen == 1))
    return NONE if home == away else (0 if home > away else 1)
