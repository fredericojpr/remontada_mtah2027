# Sign-off: 2nd-half kickoff detection (rule 10)

*Team A · 29 October 2026 · status: **open**, handed over*

## 1. The task

The pipeline labels every frame of the match `H` / `A` / `D` / `X`. Each graded half must start **dead (`D`) until its kickoff**. The organisers publish the facts this rests on (DATA.md, FAQ.md):

| | Frames | Fact |
|---|---|---|
| 1st half | from 11,185 | graded from the kickoff itself |
| 2nd half | from 110,808 | graded from here, but **kickoff is at 113,742** |
| 2nd-half pre-kickoff stretch | 110,808–113,741 (2,934 frames, 117 s) | **all `D`** in the ground truth |

**Open problem:** our pipeline labels most of that 117 s stretch as play. Anyone working on it is bound by these constraints:
- **Strict data rule.** No hosted LLM may read the gated data or anything extracted from it. Code runs locally; only aggregate numbers come back (see `team_a/pipeline.py`).
- **No hand labels** on this match, for any purpose (RULES.md).
- **No rules or constants tied to specific frames.** The published kickoff (113,742) may be used only as a **correctness check**, never inside the labelling logic, and never as a target to tune against.
- **The public 5 minutes are a correctness check only**, never a tuning set.

## 2. Where the logic lives

- `team_a/dead_ball.py`:
  - `opening_restart()`: rule 10, the half's opening restart;
  - `stoppages()`: rules 6–8, stoppages and restarts;
  - `travels()` / `kick_frames()`: the kick definition.
- `team_a/config.py`: every parameter, with its rule number and reason.
- `team_a/pipeline.py`: `checks()` / `describe()` are the correctness checks quoted below.
- `tests/test_rules.py`: one test per rule, including the rule 10 failure patterns.

Run (≈ a few seconds once the cache exists):

```bash
MTAH_DATA_DIR=<organisers' clone>/data ~/.venvs/mtah-team-a/bin/python -m team_a.pipeline --out ~/remontada_v1.csv
```

## 3. What was tried

All runs were on our match, run locally by the PM; only aggregate output was shared. On the **degraded public sample game** (Metrica Sample Game 3, our calibration proxy), every variant scored the same: spellF1 **0.376** [0.337–0.418]. The organisers' ±2 s baseline scores 0.254 [0.230–0.284] there. So the sample game **cannot tell these variants apart**: its ball is blank during stoppages, and its halves are graded from the kickoff.

| # | Commit | Rule 10 / kick definition | Possessions | Stoppages | Kickoff result | Public 5 min | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `24844bb` | Half opens on first kick; kick = ball > 3 m/s for 3 frames | 375 | 107 | FAIL (old check) | 0.412, 17/17 poss | Baseline v1 |
| 2 | `ef5cc80` | Kick = ball **travels 1.5 m in 0.5 s** (jitter-proof) | 374 | 106 | FAIL −117 s | 0.412, 17/17 | Kick definition kept; kickoff unchanged |
| 3 | `1ecbe62` | First kick **within 2 m of the centre mark** | 249 | 72 | FAIL **+1974 s** | 0.412, 17/17 | **Worse:** no centre kick seen at the real kickoff, so 33 min of the 2nd half went dead |
| 4 | `1ff9614` | First kick from the **kickoff formation** (≥ 90% of each team in its own half) | 273 | 88 | FAIL −33 s | **0.000, 0 poss** | **Worse:** formation is common in open play on our match, so the 1st half opened minutes late |
| 5 | `e281548` | **Last kick before the formation breaks** (≥ 2 s formations, 1 s bridging) | 273 | 88 | FAIL −28 s | **0.000, 0 poss** | **Worse:** same cause as #4 |
| 6 | `aa57441` | First kick **followed by 10 s without a new stoppage**, plus proper checks | 374 | 106 | FAIL (see §4) | 0.412, 17/17 | Byte-identical file to #2 (sha `0213b1b8…`) |

The "kickoff result" for runs 1–5 came from an **inadequate check**: it measured only where the *first* dead stretch of the 2nd half ended, not how much of the pre-kickoff stretch was labelled dead. Run 6 replaced it.

## 4. Diagnosis (run 6, the reliable measurement)

```
1st half: sustained play starts +0 s after its first graded frame              ✓
2nd half: pre-kickoff stretch labelled dead 19%                                ✗
          sustained play starts -117 s from the published kickoff              ✗
```

- **The 1st half is correct.**
- **In the 2nd-half pre-kickoff stretch, players and/or the ball keep moving.** So neither stoppage rule fires:
  - rule 7 (halt) needs the median player speed below 1.2 m/s with the ball missing or still;
  - rule 6 (ball out) needs the ball beyond a line.

  A kick happens near the half's first graded frame and "play" continues from there.
- **Why no rule 10 variant could work:** variants #1, #2 and #6 all wait for some stoppage-like signal before the kickoff, and there isn't one. Variants #3–#5 looked for a kickoff signal that is either missing at the real kickoff (the ball at the centre mark) or present far too often in open play (the formation).

**Score impact is small.** It is confined to 2,934 frames (1.8% of graded frames).
- About 95 s are wrongly labelled as play, roughly 8 spurious possessions at our 11.8 s mean. That's about **0.01 spellF1**, inside the ±0.04 noise band.
- macroF1 (the tie-break only) loses perhaps 0.02, through the `D` class.

## 5. Possible next steps

In order of expected value per effort:

1. **Accept for now.** The current file (sha `0213b1b8…`) validates and passes every other check, and is the recommended **1 Nov insurance submission**. The kickoff issue is polish; calibration in M2 (we under-count possessions: 278 vs 379 on the sample game) is worth more.
2. **Use Smart Tagging's automatic `Kick Off (Start)` tag as the kickoff prior.** This is the most promising lead, and was not tried because v1 kept Smart Tagging out of labelling for simplicity.
   - **Why it's allowed:** it is provided, algorithmic (not human) data. The FAQ explicitly invites its use.
   - **Why it should work:** the organisers' `starter/load_smart_tagging.py` verifies that both tagged kickoff windows contain the real kickoff. The windows open about 3.5 s early.
   - **Rule:** a half opens on the first kick at or after the start of that half's `Kick Off (Start)` window, falling back to today's rule if there is no tag. One parameter-free rule, fully explainable.
   - **To check:** the §4 lines should read ≥ 90% dead and within ±2 s. The 1st half must stay at +0 s.
3. **If more signal is needed, measure the stretch first, locally, sharing aggregates only.** Compare the pre-kickoff stretch with open play on:
   - median player speed;
   - ball visibility and speed;
   - the number of tracked players;
   - players beyond the touchlines (teams walking on);
   - team spread;
   - the ball's distance from the centre mark.

   Choose a law-of-the-game signal only if it separates the two clearly, and check it does not fire in open play. That is the test the formation idea failed.
4. **Do not:**
   - hard-code 113,742 or any frame range;
   - tune a threshold until the published kickoff check passes;
   - use the public 5 minutes to choose between variants.

   Each of these breaks RULES.md or turns a correctness check into a tuning target.

## 6. Open decisions for the PM

- **Revert `aa57441`'s "10 s of play" logic to plain first kick?** It changes nothing on our match or the sample game, so simplicity argues for reverting. In either case, keep the new check lines in `pipeline.py`.
- **Registered team name**, for the submission file names (`<team_name>.csv`, `<team_name>.md`).
