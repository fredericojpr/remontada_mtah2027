"""Make clean public tracking look like our match's automatic tracking, before calibrating on it.

Three a priori degradations, none fitted to our match's labels or scores:
  - ball gaps: our match's real ball-missing sequence over graded frames, read from the public
    evaluation/results/baseline_raw.csv (D there means the ball was not tracked), laid over the
    sample frame by frame so gap lengths and clustering are kept;
  - Gaussian position noise on ball and players;
  - player dropouts in short blocks, so about 20.5 of 22 players are seen, as in our match.

The sample's own ball is blank whenever play is dead, which ours is not, so restart timing cannot
be tested on it directly. fill_dead_ball() first puts the ball, still, where play restarts, over
every dead stretch: an a priori assumption (the ball waits at the restart spot), not a fit.
"""

import dataclasses
import os
import sys

import numpy as np

from team_a import epts
from team_a.evidence import runs

sys.path.insert(0, os.path.join(epts.ROOT, "evaluation"))
import games  # noqa: E402
import possession_metrics as pm  # noqa: E402

BASELINE_RAW = os.path.join(epts.ROOT, "evaluation", "results", "baseline_raw.csv")
BALL_NOISE_M = 0.5
PLAYER_NOISE_M = 0.2
PLAYER_DROP_SHARE = 0.07
PLAYER_DROP_BLOCK_FRAMES = 50
SEED = 0


def our_ball_missing():
    codes = pm.label_codes(pm.read_label_csv(BASELINE_RAW))
    graded = np.concatenate([np.arange(first, last + 1)
                             for _, first, last in games.half_video_blocks(games.GAME)])
    return codes[graded] == pm.D


def degrade(tracking, seed=SEED, ball_noise_m=BALL_NOISE_M, player_noise_m=PLAYER_NOISE_M,
            player_drop_share=PLAYER_DROP_SHARE):
    rng = np.random.RandomState(seed)
    n_frames, n_slots = tracking.slot_xy.shape[:2]

    missing = np.resize(our_ball_missing(), n_frames)
    ball = tracking.ball_xy + rng.normal(0, ball_noise_m, tracking.ball_xy.shape)
    ball[missing] = np.nan

    slots = tracking.slot_xy + rng.normal(0, player_noise_m, tracking.slot_xy.shape)
    n_blocks = -(-n_frames // PLAYER_DROP_BLOCK_FRAMES)
    dropped = rng.uniform(size=(n_blocks, n_slots)) < player_drop_share
    dropped = np.repeat(dropped, PLAYER_DROP_BLOCK_FRAMES, axis=0)[:n_frames]
    slots[dropped] = np.nan
    speeds = np.where(dropped, np.nan, tracking.slot_speed)

    return dataclasses.replace(tracking, ball_xy=ball, slot_xy=slots, slot_speed=speeds)


def fill_dead_ball(tracking, labels, look_ahead=25):
    """The ball, still at its restart position, on the unseen frames of every dead stretch.

    The restart position is where the ball is first seen within look_ahead frames of the restart;
    a stretch with no such sighting is left as it is.
    """
    ball = tracking.ball_xy.copy()
    for start, stop in runs(labels == pm.D):
        seen = np.flatnonzero(~np.isnan(ball[stop:stop + look_ahead, 0]))
        if not len(seen):
            continue
        stretch = ball[start:stop]
        stretch[np.isnan(stretch[:, 0])] = ball[stop + seen[0]]
    return dataclasses.replace(tracking, ball_xy=ball)
