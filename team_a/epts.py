"""Read a FIFA/EPTS tracking export (metadata XML + raw text) into numpy arrays.

Raw line: "<frame_id>:<slot>;<slot>;...:<ball>", each group "x,y[,...]" in 0-1 pitch units, NaN when
unseen. Only x and y are kept for the ball; for slots the third field (speed, m/s) is kept when the
export has one. Positions are returned in metres.
"""

import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import games  # noqa: E402

HOME, AWAY = 0, 1


@dataclass
class Tracking:
    frame_id: np.ndarray
    ball_xy: np.ndarray
    slot_xy: np.ndarray
    slot_speed: np.ndarray
    slot_team: np.ndarray
    pitch: tuple


def slot_teams(meta_path, n_slots):
    """[(first_frame_id, last_frame_id, team per column)] from the metadata.

    When the metadata lists exactly one player per column, columns follow player order (the
    organisers' convention, checked byte-for-byte by the doctor). Otherwise the columns are read
    from each DataFormatSpecification, which changes with substitutions.
    """
    root = ET.parse(meta_path).getroot()
    team_ids = [team.get("id") for team in root.iter("Team")]
    if len(team_ids) != 2:
        raise ValueError("expected 2 teams in metadata, found {}".format(len(team_ids)))
    side = {player.get("id"): HOME if player.get("teamId") == team_ids[0] else AWAY
            for player in root.iter("Player")}
    players = [player.get("id") for player in root.iter("Player")]
    if len(players) == n_slots:
        return [(None, None, np.array([side[p] for p in players], dtype=np.int8))]
    owner = {channel.get("id"): channel.get("playerId") for channel in root.iter("PlayerChannel")}
    specs = []
    for spec in root.iter("DataFormatSpecification"):
        refs = [ref.get("playerChannelId") for ref in spec.iter("PlayerChannelRef")]
        columns = [side[owner[r]] for r in refs if r.endswith("_x")]
        if len(columns) != n_slots:
            raise ValueError("format block has {} columns, raw data has {}".format(
                len(columns), n_slots))
        specs.append((int(spec.get("startFrame")), int(spec.get("endFrame")),
                      np.array(columns, dtype=np.int8)))
    return specs


def teams_per_frame(specs, frame_id):
    if specs[0][0] is None:
        return np.broadcast_to(specs[0][2], (len(frame_id), len(specs[0][2]))).copy()
    out = np.full((len(frame_id), len(specs[0][2])), -1, dtype=np.int8)
    for first, last, columns in specs:
        out[(frame_id >= first) & (frame_id <= last)] = columns
    return out


def count_slots(raw_path):
    with open(raw_path) as handle:
        return len(handle.readline().split(":")[1].split(";"))


def _slot_row(field, n_slots, number):
    groups = field.split(";")
    if len(groups) != n_slots:
        raise ValueError("line {}: {} slot groups, metadata has {}".format(
            number, len(groups), n_slots))
    row = np.full((n_slots, 3), np.nan)
    for i, group in enumerate(groups):
        values = group.split(",")[:3]
        row[i, :len(values)] = [float(v) for v in values]
    return row


def parse_raw(raw_path, n_slots):
    frame_ids, balls, slots = [], [], []
    with open(raw_path) as handle:
        for number, line in enumerate(handle, start=1):
            parts = line.rstrip("\n").split(":")
            if len(parts) != 3:
                raise ValueError("line {}: expected 3 ':'-separated parts".format(number))
            frame_ids.append(int(parts[0]))
            ball = parts[2].split(",")
            balls.append((float(ball[0]), float(ball[1])))
            slots.append(_slot_row(parts[1], n_slots, number))
    slots = np.stack(slots)
    return (np.array(frame_ids, dtype=np.int64), np.array(balls, dtype=np.float64),
            slots[:, :, :2], slots[:, :, 2])


def load(meta_path, raw_path, pitch, cache_path=None):
    if cache_path and os.path.isfile(cache_path) and (
            os.path.getmtime(cache_path) > os.path.getmtime(raw_path)):
        z = np.load(cache_path)
        return Tracking(z["frame_id"], z["ball_xy"], z["slot_xy"], z["slot_speed"],
                        z["slot_team"], pitch)
    n_slots = count_slots(raw_path)
    specs = slot_teams(meta_path, n_slots)
    frame_id, ball, slot_xy, speed = parse_raw(raw_path, n_slots)
    team = teams_per_frame(specs, frame_id)
    scale = np.array(pitch, dtype=np.float64)
    tracking = Tracking(frame_id, ball * scale, slot_xy * scale, speed, team, pitch)
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        np.savez(cache_path, frame_id=tracking.frame_id, ball_xy=tracking.ball_xy,
                 slot_xy=tracking.slot_xy, slot_speed=tracking.slot_speed,
                 slot_team=tracking.slot_team)
    return tracking


def load_match(source="tactical", game=games.GAME, data_dir=None):
    meta, raw = games.require(["atd_meta", "atd_raw"], game, data_dir, source)
    cache = os.path.join(data_dir or games.DATA_DIR, "cache", "{}_{}_v2.npz".format(game, source))
    return load(meta, raw, games.GAMES[game]["pitch"], cache)


def speeds_from_positions(slot_xy, fps=25, window=5):
    step = np.full(slot_xy.shape[:2], np.nan)
    step[1:] = np.hypot(*(slot_xy[1:] - slot_xy[:-1]).transpose(2, 0, 1)) * fps
    filled = np.nan_to_num(step)
    seen = (~np.isnan(step)).astype(np.float64)
    kernel = np.ones(window)
    total = np.apply_along_axis(np.convolve, 0, filled, kernel, "same")
    count = np.apply_along_axis(np.convolve, 0, seen, kernel, "same")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def nearest_team(tracking):
    """Team of the slot nearest the ball per frame (-1 when the ball or every slot is unseen)."""
    delta = tracking.slot_xy - tracking.ball_xy[:, None, :]
    distance = delta[:, :, 0] * delta[:, :, 0] + delta[:, :, 1] * delta[:, :, 1]
    distance = np.where(np.isnan(distance), np.inf, distance)
    nearest = np.argmin(distance, axis=1)
    team = tracking.slot_team[np.arange(len(nearest)), nearest].astype(np.int8)
    unseen = np.isnan(tracking.ball_xy[:, 0]) | np.isinf(distance.min(axis=1))
    return np.where(unseen, -1, team).astype(np.int8)
