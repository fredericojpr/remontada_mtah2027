import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from team_a import sample_game as sg  # noqa: E402

HOME, AWAY = "TA", "TB"


def event(index, kind, start, end=None, team=HOME, period=1, sub=None):
    return {"index": index, "type": {"name": kind}, "team": {"id": team}, "period": period,
            "start": {"frame": start}, "end": {"frame": end or start},
            "subtypes": {"name": sub} if sub else None}


def labels(events, n=60):
    return "".join("HADX"[c] for c in sg.event_labels(events, n, HOME))


def test_on_ball_events_set_possession_and_challenges_do_not():
    events = [event(1, "SET PIECE", 1, sub="KICK OFF"), event(2, "PASS", 5),
              event(3, "CHALLENGE", 10, team=AWAY), event(4, "RECOVERY", 15, team=AWAY),
              event(5, "PASS", 20, team=AWAY)]
    assert labels(events, 25) == "H" * 14 + "A" * 6 + "X" * 5


def test_ball_out_applies_at_its_end_and_lasts_until_the_restart():
    events = [event(1, "SET PIECE", 1, sub="KICK OFF"), event(2, "BALL OUT", 10, end=13),
              event(3, "CARRY", 10), event(4, "SET PIECE", 20, team=AWAY, sub="THROW IN"),
              event(5, "PASS", 25, team=AWAY)]
    assert labels(events, 30) == "H" * 12 + "D" * 7 + "A" * 6 + "X" * 5


def test_fouls_stop_play_but_advantage_does_not():
    foul = event(2, "CHALLENGE", 8, team=AWAY)
    foul["subtypes"] = [{"name": "GROUND"}, {"name": "FAULT"}, {"name": "WON"}]
    advantage = event(3, "CHALLENGE", 3, team=AWAY)
    advantage["subtypes"] = [{"name": "FAULT"}, {"name": "ADVANTAGE"}]
    events = [event(1, "SET PIECE", 1), advantage, foul, event(4, "SET PIECE", 12, sub="FREE KICK")]
    assert labels(events, 15) == "H" * 7 + "D" * 4 + "H" + "X" * 3


def test_periods_are_graded_separately():
    events = [event(1, "SET PIECE", 1), event(2, "PASS", 4),
              event(3, "SET PIECE", 10, team=AWAY, period=2), event(4, "PASS", 12, team=AWAY,
                                                                    period=2)]
    assert labels(events, 15) == "H" * 4 + "X" * 5 + "A" * 3 + "X" * 3
