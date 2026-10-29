"""A small synthetic match written in the provider's EPTS file formats, for tests that must not
touch the gated data."""

import os

import numpy as np

N_SLOTS = 6


def write_metadata(path, n_slots=N_SLOTS):
    players = "".join('<Player id="P{0}" teamId="{1}"><Name>Track {0}</Name>'
                      '<ShirtNumber>{0}</ShirtNumber></Player>'.format(
                          i + 1, "T1" if i < n_slots // 2 else "T2") for i in range(n_slots))
    xml = ('<?xml version="1.0"?><Main><Metadata><Teams>'
           '<Team id="T1"><Name>Home</Name></Team><Team id="T2"><Name>Away</Name></Team>'
           '</Teams><Players>{}</Players></Metadata></Main>').format(players)
    with open(path, "w") as handle:
        handle.write(xml)


def _group(x, y, s):
    if np.isnan(x):
        return "NaN,NaN,NaN"
    return "{:.5f},{:.5f},{:.2f}".format(x, y, s)


def write_raw(path, ball, slots, speeds, first_frame_id=1):
    with open(path, "w") as handle:
        for i in range(len(ball)):
            players = ";".join(_group(slots[i, j, 0], slots[i, j, 1], speeds[i, j])
                               for j in range(slots.shape[1]))
            bx, by = ball[i]
            ball_group = "NaN,NaN,NaN" if np.isnan(bx) else "{:.5f},{:.5f},0.00".format(bx, by)
            handle.write("{}:{}:{}\n".format(first_frame_id + i, players, ball_group))


def random_match(n_frames=500, seed=0, n_slots=N_SLOTS):
    rng = np.random.RandomState(seed)
    slots = rng.uniform(0, 1, (n_frames, n_slots, 2))
    speeds = rng.uniform(0, 8, (n_frames, n_slots))
    ball = rng.uniform(-0.02, 1.02, (n_frames, 2))
    ball[rng.uniform(size=n_frames) < 0.4] = np.nan
    slots[rng.uniform(size=(n_frames, n_slots)) < 0.1] = np.nan
    slots[7, :] = np.nan
    return ball, slots, speeds


def write_match(folder, n_frames=500, seed=0):
    meta = os.path.join(folder, "synth_atd.xml")
    raw = os.path.join(folder, "synth_atd.txt")
    write_metadata(meta)
    ball, slots, speeds = random_match(n_frames, seed)
    write_raw(raw, ball, slots, speeds)
    return meta, raw
