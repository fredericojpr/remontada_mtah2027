# Team A: compliance notes and data attribution

*5 November 2026. Draft material for the technical document.*

The organisers' additional guidance (5 Nov 2026) takes precedence over RULES.md, earlier emails and
earlier answers. This note records how the submission pipeline meets it.

## How the pipeline meets the guidance

- **Inputs.** The labelling code (`team_a/epts.py`, `evidence.py`, `dead_ball.py`,
  `possession.py`) reads only the provided automatic tracking and Smart Tagging. It reads no
  ground truth and no video, and it contains no rules or constants tied to specific frames of the
  provided game.
- **No hand labels.** No human-produced labels or corrections on the provided game are used, for
  any purpose. The hand-labelled "silver set" planned in DISCOVERY.md was cancelled on 27 Oct
  before any labelling.
- **Tuning on external data only.** Every parameter is in `team_a/config.py`. Only those marked
  TUNABLE may be calibrated, and only on external data (Metrica Sample Game 3, degraded to look
  like our tracking by `team_a/degrade.py`). Nothing is trained, fitted, calibrated or tuned on
  the ground-truth possession data or on the provided video.
- **No checking against the video.** Our output is not checked against the video. The video may
  be watched only to understand what counts as possession.
- **Automatic checks.** `team_a/pipeline.py` runs automatic checks that use only the provided
  data: the official validator, aggregate counts and the published facts about each half.
- **Reproducible.** Running `python -m team_a.pipeline --out <team_name>.csv` against the provided
  data regenerates the submission byte for byte; it prints the file's sha256.

## External data and attribution

| Dataset | Used for | Licence and terms | Attribution |
|---|---|---|---|
| **Metrica Sports sample data**, Sample Game 3 ([metrica-sports/sample-data](https://github.com/metrica-sports/sample-data)) | Calibrating and validating the rules (`team_a/sample_game.py`), restart timing (`team_a/scripts/restart_latency.py`) | No formal licence file. The README asks users to "be responsible with the use of this data" and to acknowledge the source in anything public. Downloaded at run time, never committed. | *Tracking and event data: Metrica Sports sample data, Sample Game 3, https://github.com/metrica-sports/sample-data.* |

Before using any other dataset (for example Sportec Open / IDSSE, CC-BY 4.0), check its licence
and add a row here. The technical document must repeat this table.
