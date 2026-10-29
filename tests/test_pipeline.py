import hashlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from team_a import epts, possession  # noqa: E402
from tests import synth  # noqa: E402

PITCH = (105.3, 68.0)


def test_labels_are_deterministic_and_graded_only_inside_halves(tmp_path):
    meta, raw = synth.write_match(str(tmp_path), n_frames=2000, seed=3)
    tracking = epts.load(meta, raw, PITCH)
    halves = [(100, 899), (1100, 1899)]
    first = possession.label_match(tracking, halves, 2000)
    second = possession.label_match(tracking, halves, 2000)
    assert hashlib.sha256(first.tobytes()).hexdigest() == hashlib.sha256(second.tobytes()).hexdigest()
    graded = np.zeros(2000, dtype=bool)
    for a, b in halves:
        graded[a:b + 1] = True
    assert (first[~graded] == possession.X).all()
    assert not (first[graded] == possession.X).any()
