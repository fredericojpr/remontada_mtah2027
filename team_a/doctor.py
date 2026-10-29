"""PASS/FAIL checks on the gated match data. Prints no data values, so its output can be shared.

    MTAH_DATA_DIR=<data folder> python -m team_a.doctor
"""

import hashlib
import os
import sys

import numpy as np

from team_a import epts

ROOT = epts.ROOT
sys.path.insert(0, os.path.join(ROOT, "starter"))
import baseline  # noqa: E402
import games  # noqa: E402
import load_homography  # noqa: E402
import load_smart_tagging  # noqa: E402

N_FRAMES = games.source_frames("tactical")
BASELINE_RAW = os.path.join(ROOT, "evaluation", "results", "baseline_raw.csv")
OUT_OF_PITCH_MARGIN_M = 0.5
PLAUSIBLE_MEDIAN_SPEED_MPS = (0.3, 4.0)

results = []


def report(status, name, detail=""):
    results.append(status)
    print("{:<5} {}{}".format(status, name, "  ({})".format(detail) if detail else ""))


def check(name, func):
    try:
        outcome = func()
    except Exception as error:
        report("FAIL", name, type(error).__name__)
        return None
    if isinstance(outcome, tuple):
        ok, detail = outcome
    else:
        ok, detail = outcome, ""
    report("PASS" if ok else "FAIL", name, detail)
    return ok


def files_present():
    games.require(list(games.SOURCES["tactical"]["assets"]))
    return True


def graded_mask():
    mask = np.zeros(N_FRAMES, dtype=bool)
    for _, first, last in games.half_video_blocks(games.GAME):
        mask[first:last + 1] = True
    return mask


def main():
    print("data folder: {}\n".format(games.DATA_DIR))
    if not check("all tactical files present", files_present):
        return 1

    state = {}

    def load():
        state["t"] = epts.load_match("tactical")
        return True
    if not check("tracking parses (cache built on first run)", load):
        return 1
    t = state["t"]

    check("one record per video frame, frame_id 1..N",
          lambda: len(t.frame_id) == N_FRAMES
          and np.array_equal(t.frame_id, np.arange(1, N_FRAMES + 1)))
    check("two teams, every slot assigned", lambda: set(np.unique(t.slot_team).tolist()) == {0, 1})

    def rebuild_baseline_raw():
        codes = np.full(N_FRAMES, -1, dtype=np.int8)
        codes[t.frame_id - 1] = epts.nearest_team(t)
        labels = baseline.smooth(codes, 0)
        text = "frame,label\n" + "".join("{},{}\n".format(i, l) for i, l in enumerate(labels))
        ours = hashlib.sha256(text.encode()).hexdigest()
        theirs = hashlib.sha256(open(BASELINE_RAW, "rb").read()).hexdigest()
        return ours == theirs, "sha256 match" if ours == theirs else "sha256 differs"
    check("our parser rebuilds baseline_raw.csv byte for byte", rebuild_baseline_raw)

    def speed_field():
        speeds = t.slot_speed[graded_mask()[t.frame_id - 1]]
        if np.isnan(speeds).all():
            return False, "no speed field in export"
        low, high = PLAUSIBLE_MEDIAN_SPEED_MPS
        return low <= float(np.nanmedian(speeds)) <= high, "median within plausible range"
    check("slot speed field present and plausible", speed_field)

    length, width = t.pitch
    x, y = t.ball_xy[:, 0], t.ball_xy[:, 1]
    beyond = ((x < -OUT_OF_PITCH_MARGIN_M) | (x > length + OUT_OF_PITCH_MARGIN_M)
              | (y < -OUT_OF_PITCH_MARGIN_M) | (y > width + OUT_OF_PITCH_MARGIN_M))
    report("INFO", "ball positions beyond the lines",
           "present: rule 6 active" if beyond.any() else "absent: rule 6 inert, rule 7 only")

    check("smart tagging time base matches both kickoffs",
          lambda: load_smart_tagging.check_time_base(load_smart_tagging.load())["agrees"])
    check("homography one row per video frame",
          lambda: load_homography.check_alignment()["agrees"])

    failed = results.count("FAIL")
    print("\n{} checks, {} failed".format(results.count("PASS") + failed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
