"""Metrica Sample Game 3 (public, another match): tracking plus possession labels derived from its
events. Used only to calibrate and validate rules; never part of the submission.

Source: https://github.com/metrica-sports/sample-data (Metrica Sports). Event frames are tracking
frame ids.

Labels, by algorithm:
  - an on-ball event (pass, carry, recovery, shot, set piece) makes its team the possessor and
    ends any stoppage;
  - a stoppage event (ball out, foul, offside, hand ball, goal) makes the ball dead until the next
    on-ball event;
  - challenges and ball-lost events change nothing (the opponent's next on-ball event does);
  - events apply where they take effect: on-ball events at their start, stoppages at their end
    (a ball-out event starts at the last touch and ends when the ball crosses the line);
  - each period is graded from its first event to its last; everything else is X.
"""

import json
import os
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np

from team_a import epts

FOLDER = os.path.join(epts.ROOT, "data", "external", "metrica_sample_game_3")
BASE_URL = "https://raw.githubusercontent.com/metrica-sports/sample-data/master/data/Sample_Game_3/"
FILES = {"meta": "Sample_Game_3_metadata.xml", "raw": "Sample_Game_3_tracking.txt",
         "events": "Sample_Game_3_events.json"}
PITCH = (105.0, 68.0)
H, A, D, X = 0, 1, 2, 3

ON_BALL = {"PASS", "CARRY", "RECOVERY", "SHOT", "SET PIECE"}
STOPPING_SUBTYPES = {"FAULT", "OFFSIDE", "HAND BALL", "GOAL"}


def path(name):
    return os.path.join(FOLDER, FILES[name])


def download():
    os.makedirs(FOLDER, exist_ok=True)
    for name in FILES:
        if not os.path.isfile(path(name)):
            urllib.request.urlretrieve(BASE_URL + FILES[name], path(name))


def load_tracking():
    download()
    tracking = epts.load(path("meta"), path("raw"), PITCH, os.path.join(FOLDER, "cache_v2.npz"))
    if np.isnan(tracking.slot_speed).all():
        tracking.slot_speed = epts.speeds_from_positions(tracking.slot_xy)
    return tracking


def load_events():
    download()
    with open(path("events")) as handle:
        return json.load(handle)["data"]


def subtypes(event):
    value = event.get("subtypes")
    if not value:
        return set()
    return {s["name"] for s in (value if isinstance(value, list) else [value])}


def is_stoppage(event):
    kind = event["type"]["name"]
    if kind == "BALL OUT":
        return True
    if kind == "FAULT RECEIVED":
        return True
    sub = subtypes(event)
    if kind == "CHALLENGE":
        return "FAULT" in sub and "ADVANTAGE" not in sub
    return bool(sub & STOPPING_SUBTYPES) and kind in {"BALL LOST", "SHOT"}


def event_labels(events, n_frames, home_team_id):
    labels = np.full(n_frames, X, dtype=np.int8)
    for period in sorted({e["period"] for e in events}):
        chunk = [e for e in events if e["period"] == period]
        first = min(e["start"]["frame"] for e in chunk) - 1
        last = max(e["end"]["frame"] for e in chunk) - 1
        effects = []
        for event in chunk:
            if is_stoppage(event):
                effects.append((event["end"]["frame"] - 1, event["index"], D))
            elif event["type"]["name"] in ON_BALL:
                team = H if event["team"]["id"] == home_team_id else A
                effects.append((event["start"]["frame"] - 1, event["index"], team))
        state, frame = D, first
        for at, _, new in sorted(effects):
            labels[frame:at] = state
            state, frame = new, max(frame, at)
        labels[frame:last + 1] = state
    return labels


def home_team_id():
    return next(ET.parse(path("meta")).getroot().iter("Team")).get("id")


def load_labels(n_frames):
    return event_labels(load_events(), n_frames, home_team_id())
