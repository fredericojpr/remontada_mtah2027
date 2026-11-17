# Ball possession from automatic tracking: a rule-based pipeline

*Team A · More than a Hack 2027, Phase 1 · 17 November 2026*

Repository: https://github.com/fredericojpr/remontada_mtah2027 · Code in `team_a/` · Regenerate
with `python -m team_a.pipeline --out <team_name>.csv` (section 6).

---

## 1. Approach

We label every frame of the tactical video `H`, `A` or `D` with a small, deterministic,
rule-based system. It has ten rules, each with a football reason, and 19 parameters, all in
[`team_a/config.py`](config.py). Nothing is learned. The code uses numpy and pandas only, runs on a
CPU and gives the same file on every run.

**Why rules and not a learned model.** Three things decided it.

1. **The score rewards clean structure more than per-frame accuracy.** `spellF1` counts whole
   possessions recovered. The organisers' baselines already reach 78–89% frame-level team accuracy
   on the public window, yet `spellF1` stays at 0.04–0.42, because nearest-player labels flip
   whenever a defender passes near the ball. The fix is structural: possession must change only on
   positive evidence that the other team has won control. A state machine says that directly.
2. **We had no labelled data in our match's convention.** The rules forbid hand labels on the
   provided game, and the organisers' guidance of 5 November requires anything fitted or tuned to
   use external data only. The one external dataset we used, Metrica Sample Game 3, is a single
   match whose possession labels we had to derive from events (section 3). That is enough to
   evaluate a handful of explainable rules. It is not enough to train a model that would then have
   to transfer across providers, a transfer the literature reports as poor.
3. **Every decision has to be explainable and reproducible.** A rule with one parameter and a
   football reason can be checked by a reader. A model fitted on one sample game cannot.

**Pipeline** (`team_a/pipeline.py`):

```
tactical ATD ──► clean ball (rule 1) ──► team control per frame (rule 2) ──► gains (rules 3, 5)
                                                                                  │
tactical ATD ──► ball out, collective halt, kicks (rules 6–8)                     │
Smart Tagging ─► kickoff windows (rule 10) ──► stoppages [dead_from, restart) ────┤
                                                                                  ▼
                                    per-half state machine: D until kickoff, then H/A,
                                    switching only on a gain by the other team (rule 4);
                                    D during stoppages, restart team by rule 9
                                                                                  │
                                                                                  ▼
                                    CSV ──► official validator ──► sha256
```

Frames outside the two graded halves are written `X`. No graded frame is ever `X`.

---

## 2. The possession rules

All distances are in metres and times in frames at 25 fps. Code references are to `team_a/`.

| # | Rule | Parameters | Reason |
|---|---|---|---|
| **1** | **Ball cleaning.** Fill ball gaps of up to 10 frames (0.4 s) linearly; smooth with a 5-frame moving average, only inside stretches where the ball is seen, never across a gap (`evidence.clean_ball`) | `ball_gap_fill_frames` 10, `ball_smooth_frames` 5 | Short gaps are tracking jitter; long gaps are real occlusions and must not get an invented path |
| **2** | **Control.** A team controls the ball on a frame when its nearest player is within 1.5 m of it **and** at least 0.5 m closer than the nearest opponent (`evidence.control`) | `control_radius_m` 1.5, `control_margin_m` 0.5 | One stride plus tracking error. The margin means a 50/50 challenge gives control to nobody |
| **3** | **Gain.** A spell of control counts only if it lasts 8 frames (0.32 s), bridging dropouts of up to 2 frames (`evidence.gains`) | `gain_frames` 8, `gain_dropout_frames` 2 | A passing ball (> ~9 m/s) cannot stay within 1.5 m of a player for 0.32 s, so a pass going past a defender is not a gain |
| **4** | **Change of possession.** While the ball is alive, possession changes **only** on a gain by the other team. A loose ball, a deflection, a touch or a challenge without control leaves possession with the last team (`possession.label_half`) | — | CHALLENGE.md's definition: a change of possession needs *controlled* possession by the opponent |
| **5** | **Gains hidden by a ball gap.** If a gain starts straight after a ball gap, the switch is dated to mid-gap, at most 2 s back (`evidence.gains`) | `gap_backdate_max_frames` 50 | The ball changed hands somewhere in the gap; mid-gap is the unbiased guess |
| **6** | **Ball out.** Dead from the frame the ball is 0.5 m beyond a line for 3 frames (`dead_ball.stoppages`) | `out_margin_m` 0.5, `out_frames` 3 | The whole ball must be over the line, plus a margin for jitter |
| **7** | **Collective halt.** Dead when the median player speed is below 1.2 m/s for 3 s while the ball is missing or still (< 1 m/s) | `halt_speed_mps` 1.2, `halt_frames` 75, `still_ball_mps` 1.0 | Fouls, offsides and injuries stop everyone. Requiring a missing or still ball keeps slow build-up play alive. **A missing ball on its own is never a stoppage** |
| **8** | **Restart.** Play restarts on the first **kick**: the in-pitch ball travels ≥ 1.5 m within 12 frames (0.48 s), dated to the first frame faster than that average speed. After a halt, play also restarts when players move again (median > 1.2 m/s) with the ball unseen for 1 s. Stoppages closer than 2 s are merged; stoppages shorter than 2 s are dropped (`dead_ball.travels`, `kick_frames`, `stoppages`) | `kick_distance_m` 1.5, `kick_window_frames` 12, `resume_frames` 25, `min_play_frames` 50, `min_stoppage_frames` 50 | A set piece is a kick. Tracking jitter cannot move the ball 1.5 m in half a second, so the rule does not fire on a still ball |
| **9** | **Restart team.** The team nearest the ball more often in the last second before the restart; if that is a tie or nobody is seen, the team of the first gain after the restart (`dead_ball.restart_team`) | `taker_window_frames` 25 | The taker stands over the ball |
| **10** | **Half opening.** Each half is `D` until its kickoff. The kickoff is the first kick at or after the start of that half's Smart Tagging `Kick Off (Start)` window that is followed by 10 s without a new stoppage. A half with no such tag falls back to the kicks alone (`dead_ball.kickoff_tag_starts`, `opening_restart`) | `opening_play_frames` 250 | Players tap the ball about before a kickoff; the real kickoff is followed by play. Smart Tagging is automatic, provided data |

**Where we drew the lines**

- **Loose balls** stay with the last team in possession (rule 4). A loose ball never becomes `D`,
  and never flips possession until somebody controls it.
- **Challenges.** A challenge changes possession only if the challenger then *controls* the ball:
  within 1.5 m, 0.5 m clear of the opponent, for 0.32 s (rules 2–3). Winning a header or poking
  the ball away is not enough on its own.
- **Restarts.** The ball is dead from when it goes out or play halts (rules 6–7) until the restart
  kick (rule 8). The restart goes to the team at the ball (rule 9). We do not try to say who
  "owns" a dead ball; it is simply `D`.
- **Missing ball.** When the ball is not tracked, the state is carried forward. Only rule 7 can
  create a stoppage without the ball, and it needs the whole team to stop.

The logic contains **no frame numbers, frame ranges or constants tied to specific frames of the
provided game.** The published second-half kickoff (frame 113,742) appears only in
`pipeline.checks()`, as a correctness check that is printed and never read by the labelling.

---

## 3. Assets and data

### Provided assets

| Asset | Used? | How |
|---|---|---|
| Tactical automatic tracking (ATD) | **Yes, the main input** | Ball and player positions, player speeds, team of each slot from the metadata (`team_a/epts.py`) |
| Smart Tagging | **Yes, narrowly** | Only the start of each half's `Kick Off (Start)` window, for rule 10. We tried no other tag |
| Organisers' public baseline (`evaluation/results/baseline_raw.csv`) | Indirectly | Its `D` frames mark where the ball is not tracked on our match. We used that mask to degrade the sample game (section 4). It contains no ground-truth information |
| Public 5-minute ground truth | **Correctness check only** | Printed by the pipeline to confirm alignment and file format. Never used to choose between versions or set a parameter |
| Homography | No | Our rules work in pitch coordinates, which the ATD already gives |
| Broadcast video and broadcast ATD | No | Aligning a second feed was judged high effort for uncertain gain |
| Tactical video | No | The pipeline does not read it. No output was checked against it |

### External data

| Dataset | Used for | Licence and attribution |
|---|---|---|
| **Metrica Sports sample data, Sample Game 3** ([metrica-sports/sample-data](https://github.com/metrica-sports/sample-data)). 143,761 frames at 25 fps, 3,620 events | Evaluating rule variants (`team_a/sample_game.py`), restart timing (`team_a/scripts/restart_latency.py`) | No formal licence file. The README asks users to "be responsible with the use of this data" and to credit the source. **Tracking and event data: Metrica Sports sample data, Sample Game 3, https://github.com/metrica-sports/sample-data.** Downloaded at run time, never committed |

### Training data

**No model is trained, so there is no training set.** No hand-labelled data of any kind was used,
on any game. The hand-labelled validation set planned at the start of the project was cancelled on
27 October, before any labelling, when the organisers banned hand labels on the provided game.

The only labelled data we used is **Metrica Sample Game 3**, which is another match:

- **Source:** Metrica Sports' public sample data (above).
- **Who labelled it:** Metrica Sports produced the event data. How they produced it is not
  documented. We added no labels of our own.
- **How we turned it into possession labels** (by algorithm, `sample_game.event_labels`): an
  on-ball event (pass, carry, recovery, shot, set piece) gives its team possession; a stoppage
  event (ball out, foul, offside, hand ball, goal) makes the ball dead until the next on-ball
  event; challenges and ball-lost events change nothing.
- **How much:** 142,698 graded frames, 379 possessions, 90 set pieces.

None of it comes from the provided game.

---

## 4. Validation, and how parameters were set

**The parameters are a priori values**, each set from the reason in the table in section 2. A
value changed only when the rule it belongs to was redefined (the kick definition of rule 8 and
the opening rule 10, below). Three are marked TUNABLE in `config.py` (rules 2, 3 and 7). They may
be calibrated, but only on external data, and we have **not** calibrated them: one sample game, with
a noise band of about ±0.04 spellF1, cannot separate nearby values reliably.

The sample game was used to decide between rule **variants**, never between values on our match.
Clean public tracking is far better than ours, so we first degrade it (`team_a/degrade.py`) with
three a priori changes:

- our match's ball-missing pattern laid over it frame by frame, so gap lengths and clustering
  match ours;
- Gaussian noise on positions (0.5 m on the ball, 0.2 m on players);
- player dropouts in 2 s blocks, so about 20.5 of 22 players are seen, as on our match.

The sample's ball is blank whenever play is dead, which ours is not, so a third proxy also puts the
ball, still, at its restart spot during dead stretches (`degrade.fill_dead_ball`).

**Results on the sample game** (`python team_a/scripts/restart_latency.py`, 1,000-sample bootstrap):

| Proxy | spellF1 [95% CI] | macroF1 | Possessions (truth 379) |
|---|---|---|---|
| Clean | 0.553 [0.515–0.590] | 0.802 | 366 |
| Degraded | 0.376 [0.335–0.416] | 0.721 | 278 |
| Degraded, dead ball filled | 0.397 [0.359–0.437] | 0.684 | 289 |

The organisers' ±2 s baseline scores 0.254 [0.230–0.284] on the degraded sample.

**Automatic checks on our match** (printed by `pipeline.py`; only aggregate values):

- the file passes the official validator;
- 371 possessions and 105 stoppages over the match;
- the 1st half goes live at its first graded frame;
- 100% of the 2nd half's pre-kickoff stretch is `D`, and play starts 3.4 s after the published
  kickoff (section 5);
- on the public 5 minutes, 17 of 17 possessions and spellF1 0.412. This confirms that frames line
  up and labels mean what we think. With 17 possessions its noise band is about ±0.3, so it ranks
  nothing.

**Variants tried and dropped**

| Variant | Why dropped |
|---|---|
| Kick = ball faster than 3 m/s for 3 frames | Fires on tracking jitter. Replaced by "ball travels 1.5 m in 0.48 s" |
| Kickoff = first kick within 2 m of the centre mark | No centre kick is seen at the real 2nd-half kickoff, so 33 minutes went dead |
| Kickoff = first kick from the kickoff formation (≥ 90% of each team in its own half), and "last kick before the formation breaks" | The formation is common in open play on our match, so the 1st half opened minutes late |
| Backdating restarts hidden by a ball gap to mid-gap, as rule 5 does for gains | +0.003 spellF1 on the fair proxy (noise), while 21–43% of restarts came out early on the other proxies. Kept in commit `12670ba` for reproduction only |
| A masked state machine with learned switch costs, and a learned dead-ball model on player motion | Planned. With one external match for fitting and no labels in our convention, we chose to ship explainable rules instead |
| Sportec Open / IDSSE data (CC-BY 4.0) | Not used. How its possession codes are produced is undocumented, and time ran out before the audit we planned |
| Majority-vote and median smoothing of per-frame labels (the baseline approach) | Trades away short real possessions to remove flips. Rules 3–4 remove flips without that cost |

---

## 5. Limitations

- **Restarts hidden by ball gaps come out late.** When the ball is unseen at a restart, rule 8
  waits for it to reappear and travel. On the degraded sample, half of all restarts have a gap in
  the kick window, and those come out a median of 1.8–2.3 s late. We estimate the cost on our
  match at about 0.02–0.05 spellF1.
- **Taps are missed.** A restart that moves the ball less than 1.5 m in 0.48 s is not a kick to
  rule 8. Our 2nd-half kickoff comes out 3.4 s late, with the ball tracked throughout, most likely
  for this reason. Taps are 3 of 90 restarts on the sample game, so we did not loosen a rule that
  keeps us safe from jitter.
- **We under-count possessions.** 278–289 against 379 on the degraded sample. Short possessions
  lost in ball gaps, and quick exchanges below 0.32 s of control, are merged into their
  neighbours.
- **Some stoppages are not found.** 21–28 of the sample's 90 set pieces get no predicted stoppage,
  partly because the sample's ball is blank during dead play (an artefact of the proxy), but
  partly because short stoppages are dropped by design.
- **2D only.** We do not know the ball's height, so a high ball over a player counts as close to
  that player. Rule 3's 0.32 s requirement limits the damage.
- **The parameters are uncalibrated.** They are reasoned values. They have been evaluated on one
  external match, which is not enough to tune them.

**With more time:** a restart cue that does not need the ball (players accelerating together at a
restart), checked first on the fair proxy; a motion-based dead-ball model fitted on several
external matches; the masked decoder with context-dependent switch costs; and IDSSE, after an
audit of how its possession codes are made.

---

## 6. Reproduction

Requirements: Python 3.11, the match data bundle, and internet access the first time the sample
game is used (the submission itself does not need it).

```bash
git clone https://github.com/fredericojpr/remontada_mtah2027.git
cd remontada_mtah2027
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-team_a.txt

# The data bundle, unpacked into ./data or anywhere else:
export MTAH_DATA_DIR=/path/to/data

python -m team_a.doctor                              # PASS/FAIL checks on the data, no values printed
python -m team_a.pipeline --out <team_name>.csv      # writes the file, prints checks and sha256
python evaluation/validate_submission.py <team_name>.csv
```

The pipeline is deterministic: the same data gives the same file byte for byte, and it prints the
file's sha256 so a reproduction can be compared exactly. The first run parses the tracking export
and caches it in `$MTAH_DATA_DIR/cache/`; later runs take a few seconds.

Other commands:

```bash
pytest tests                                         # 34 tests on synthetic scenes, no data needed
python team_a/scripts/restart_latency.py             # the sample-game results in section 4
```

Pinned dependencies: `numpy==2.2.6`, `pandas==2.2.3`, `pytest==8.3.5` (tests only).
