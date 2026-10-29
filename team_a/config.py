"""Every parameter of the possession rules. Distances in metres, times in frames at 25 fps.

Only the three marked TUNABLE may be calibrated, and only on the public sample game; every other
value is fixed by the reason given beside it.
"""

from dataclasses import dataclass

FPS = 25


@dataclass(frozen=True)
class Params:
    # Rule 1: short gaps are tracking jitter, long gaps are real occlusions.
    ball_gap_fill_frames: int = 10
    ball_smooth_frames: int = 5

    # Rule 2: one stride plus tracking error, and clearly closer than the challenger. TUNABLE.
    control_radius_m: float = 1.5
    control_margin_m: float = 0.5

    # Rule 3: a passing ball (> ~9 m/s) cannot stay within 1.5 m for 0.32 s. TUNABLE.
    gain_frames: int = 8
    gain_dropout_frames: int = 2

    # Rule 5: backdate a switch hidden by a ball gap to mid-gap, at most 2 s.
    gap_backdate_max_frames: int = 50

    # Rule 6: the whole ball is over the line, with a jitter margin.
    out_margin_m: float = 0.5
    out_frames: int = 3

    # Rule 7: fouls, offsides and injuries stop everyone. TUNABLE.
    halt_speed_mps: float = 1.2
    halt_frames: int = 75
    still_ball_mps: float = 1.0

    # Rule 8: a set piece is a kick: the ball travels, which tracking jitter cannot fake.
    kick_distance_m: float = 1.5
    kick_window_frames: int = 12
    min_stoppage_frames: int = 50
    min_play_frames: int = 50
    resume_frames: int = 25

    # Rule 10: at a kickoff every player is in his own half (Law 8); allow one or two tracking
    # errors per team, and require most of each team to be seen.
    kickoff_own_half_share: float = 0.9
    kickoff_min_players: int = 7
    # Teams line up for seconds, not instants; after the kick, attackers cross halfway within
    # seconds, so the kickoff is the last kick shortly before the formation breaks.
    kickoff_formation_min_frames: int = 50
    kickoff_break_frames: int = 125

    # Rule 9: the taker stands over the ball in the last second before the restart.
    taker_window_frames: int = 25


DEFAULT = Params()
