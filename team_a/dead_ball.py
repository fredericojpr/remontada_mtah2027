"""Rules 6-9: when the ball goes dead, when play restarts, and who restarts it."""

import warnings

import numpy as np

from team_a.config import FPS
from team_a.evidence import NONE, runs


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


KICKOFF_CODE = "set pieces"
KICKOFF_TYPE = "kick off (start)"
HALF_TAGS = {"1st half": 1, "2nd half": 2}


def kickoff_tag_starts(events):
    """{half number: first frame of its Smart Tagging 'Kick Off (Start)' window} (rule 10).

    events as returned by starter/load_smart_tagging.load(). Matched case-insensitively; a half
    with no such tag is absent, and the opening rule then falls back to the kicks alone.
    """
    out = {}
    for event in events:
        tags = {k.lower(): (v or "").strip().lower() for k, v in event["tags"].items()}
        if ((event["code"] or "").strip().lower() == KICKOFF_CODE
                and tags.get("type") == KICKOFF_TYPE and tags.get("half") in HALF_TAGS):
            half = HALF_TAGS[tags["half"]]
            out[half] = min(out.get(half, event["start_frame"]), event["start_frame"])
    return out


def opening_restart(kicks, stoppage_starts, n, params):
    """(restart, branch): the first kick after which play runs on without a new stoppage for the
    opening-play window (rule 10). Taps before a kickoff are followed by players standing still
    again; the kickoff is followed by play. With a zero window this is simply the first kick."""
    later = np.array(stoppage_starts, dtype=np.int64)
    for kick in kicks:
        if not np.any((later > kick) & (later <= kick + params.opening_play_frames)):
            return int(kick), "first kick followed by play"
    if len(kicks):
        return int(kicks[0]), "first kick"
    return n, "no kick found"


def stoppages(ball, speed, median_speed, pitch, first, last, params, report=None,
              kickoff_tag=None):
    """[(dead_from, restart_at)] inside one graded half, frames [first, last].

    Rule 6: ball out. Rule 7: collective halt. Rule 8: restart on a kick, or when players move
    again with the ball unseen after a halt. Rule 10: each half starts dead until its kickoff;
    with a Smart Tagging kickoff window starting at frame kickoff_tag, kicks before it are not
    the kickoff.
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
    candidates, prefix = kicks, ""
    if kickoff_tag is not None:
        tagged = kicks[kicks >= kickoff_tag - first]
        candidates, prefix = ((tagged, "kickoff tag, ") if len(tagged)
                              else (kicks, "no kick after kickoff tag, "))
    opening, branch = opening_restart(candidates, [f for f, _ in starts], stop - first, params)
    branch = prefix + branch
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
