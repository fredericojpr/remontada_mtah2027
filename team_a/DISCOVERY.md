# Team A — Project Discovery: More than a Hack 2027, Phase 1 (Ball Possession)

| | |
|---|---|
| **Prepared by** | Project Manager, Team A |
| **Date** | Wednesday 21 October 2026 |
| **Status** | **v1.2.** Discovery complete for the repository and Challenge 1, with the Research Lead's literature memo merged in (v2, 22 Oct, which answers our follow-up questions). The gated match data has **not** been unpacked yet. |
| **Sources** | Every file in `metrica-sports/more-than-a-hack-2027` at commit `3de6b60`; our own runs of the official scorer and analysis scripts (`team_a/scripts/`); the Research Lead's memo *"Turning possession research into Team A's Phase 1 plan"* (21 Oct 2026). |
| **Literature figures** | Figures marked **†** come from the literature via the Research Lead's memo. Their source locations and verification status are in §18.4. The Research Lead re-verified most of them against the source text; the exceptions are flagged ⚠ there. Two decision-critical sources still get an independent spot-check (A1). |
| **Deadline** | **Tuesday 17 November 2026**, 27 days from today |


> **⚠ Superseded in part (27 Oct 2026).** The organisers' rule update (upstream `f8f2629`) bans hand labels on the provided game for any purpose, including validation, and forbids tuning on the public 5 minutes. The **silver set** (§11.4) and every "calibrate on public + silver" step in this document are therefore **void**. Calibration now uses Metrica's public sample games (other games, allowed). See the execution plan.
---

## Contents

0. [TL;DR](#0-tldr)
1. [The challenge in one page](#1-the-challenge-in-one-page)
2. [Rules and compliance: what can get us disqualified](#2-rules-and-compliance-what-can-get-us-disqualified)
3. [The data](#3-the-data)
4. [What "possession" means here](#4-what-possession-means-here)
5. [The public ground truth, dissected](#5-the-public-ground-truth-dissected)
6. [How we are scored](#6-how-we-are-scored)
7. [Metric sensitivity: which mistakes cost the most](#7-metric-sensitivity-which-mistakes-cost-the-most)
8. [The baseline, dissected](#8-the-baseline-dissected)
9. [Key insights](#9-key-insights)
10. [Solution space and recommended direction](#10-solution-space-and-recommended-direction)
11. [Validation strategy, with no leaderboard](#11-validation-strategy-with-no-leaderboard)
12. [Team structure and workstreams](#12-team-structure-and-workstreams)
13. [Plan and milestones](#13-plan-and-milestones)
14. [Risks and mitigations](#14-risks-and-mitigations)
15. [Open questions](#15-open-questions)
16. [Day-1 data unpacking checklist](#16-day-1-data-unpacking-checklist)
17. [Engineering conventions](#17-engineering-conventions)
18. [Appendix](#18-appendix)

---

## 0. TL;DR

**The task.** We get one full LaLiga match (FC Barcelona vs Athletic Club, 2024-25, matchday 2) and label each of its **199,319 video frames** `H` (Barça has the ball), `A` (Athletic has it), `D` (dead ball) or `X` (abstain). The deliverable is one CSV. A script scores it against a private ground truth (GT) for the full match. There is no jury.

**The ranking metric is `spellF1`, not per-frame accuracy.** It treats each possession as one object and matches predicted possessions one-to-one to true ones by temporal overlap (IoU 0.3–0.7). **The floor to beat is 0.2433.** `macroF1` (per-frame) only breaks ties.

**The five things that matter most:**

1. **This is a segmentation problem, not a classification problem.** On the public window, the published baselines get frame-level team accuracy of 78–89% and about 0.90 F1 on the alive/dead call, yet spellF1 is only 0.04–0.42 (0.05–0.24 on the full match). The per-frame signal is decent. The temporal structure is what's broken.
2. **Spurious flips are the main killer.** Every structural error costs about one possession (0.04–0.08 on the public window), so what matters is how often each one happens, and flips happen most. On the public GT, injecting 10 short false team-flips drops a perfect spellF1 to **0.58**. Missing every possession shorter than 4 s drops it to **0.56**, and 6 of the 17 public possessions *are* shorter than 4 s. We have to be decisive in both directions, so a wider smoothing window can't fix this.
3. **A missing ball is not a dead ball.** The baseline writes `D` whenever the ball is not tracked. Over the full match the ball is missing on 41% of graded frames, but on dead-ball frames in the public window it is still *visible* 66% of the time. Each false stoppage costs about 0.04 spellF1, and the ball gaps give the baseline a great many chances to invent one: inserting one into each of the 8 long public possessions costs **0.39**.
4. **The public 5 minutes are a correctness check, not a leaderboard.** They hold 17 possessions, and the bootstrap noise band on them is **~0.23–0.33** spellF1, against ~0.04 on the full match. The public window is also unrepresentatively easy: the ball is missing on **11.8%** of its frames against **~42%** for the rest of the match. Any choice we make by tuning on it is a coin flip.
5. **Compliance is our largest non-technical risk.** The terms prohibit making the data, or any extract of it, available to any third-party hosted or cloud LLM. That includes coding assistants like the one that produced this document. We need working rules for this before the data is unpacked (§2).

**Recommended direction:** a three-layer pipeline: (A) per-frame signals → (B) calibrated evidence for H/A/D and for candidate boundaries → (C) a **temporal decoder** that outputs whole possessions. The research memo sharpens three parts of this:

- **The decoder** becomes a small **masked state machine with "in-flight" sub-states and context-dependent switch costs**. A turnover is only allowed through an opponent *reception*, so a defender standing near the ball cannot flip the label. Published work on our failure mode (PathCRF†) reports the same over- and under-switching we saw in §8, fixed this way.
- **The dead-ball detector** is learned from **collective player movement** (published at 0.80 stoppage F1 without the ball†). Motion, set-piece geometry, ball-out and Smart Tagging cues are fused into **one calibrated stoppage probability**, with its threshold chosen by spellF1.
- **Calibration data** comes from **public, labelled tracking datasets from other matches** (Sportec/IDSSE†, Metrica samples), degraded to look like our ATD. How IDSSE's possession codes were produced is undocumented, so an **S1 audit gives a go/no-go** on using them as boundary labels. Our own hand-labelled validation set and the public window are kept for the last few knobs. RULES.md explicitly allows external data, so only the details need confirming (Q7).

Submit a safe v1 to the form by **1 November** as insurance.

**Next 72 hours:** kickoff meeting and owners (§12) · send compliance questions **and Q7** to organisers (§15) · send the two remaining follow-ups to the Research Lead (§15) · every member enrolled with T&Cs accepted · data unpacked **outside OneDrive** · baseline reproduced byte-for-byte (§16) · spot-check the two decision-critical † sources (A1).

---

## 1. The challenge in one page

| | |
|---|---|
| **Organisers** | Metrica Sports, FC Barcelona (Barça Innovation Hub), Mobile World Capital Barcelona. Talent Arena, Barcelona |
| **Match** | FC Barcelona (**home, `H`**) vs Athletic Club (**away, `A`**), LaLiga EA Sports 2024-25, matchday 2 |
| **Input** | Tactical video plus broadcast video; automatic tracking (ATD) with ball for both; automatic Smart Tagging (tactical only); per-frame homography for both |
| **Output** | `frame,label` CSV, **exactly 199,319 rows**, frames `0…199318` in order, labels `H`/`A`/`D`/`X` |
| **Graded frames** | 158,857, covering both halves. Everything else is ignored |
| **Ranked on** | `spellF1`: mean possession-spell F1 over IoU {0.3, 0.4, 0.5, 0.6, 0.7} |
| **Tie-breaks** | `macroF1` → transition F1 at ±25 frames → mean absolute latency → filename |
| **Floor** | `baseline_smooth50`, spellF1 **0.2433** (full match) |
| **GT we get** | First 5 minutes of play (frames 11,185–18,684): 17 possessions |
| **Deliverables** | (1) possession CSV, which is scored; (2) **public** code repo that regenerates the **identical** file; (3) short technical document (PDF/MD) |
| **Submission** | One Google Form per team (Google account needed), editable; the last response before the deadline counts. **No leaderboard, no feedback** |
| **File naming** | `<team_name>.csv` and `<team_name>.pdf`. The scorer names the board row after the file |
| **Team size** | 3–5 members. Under 3 is not eligible for the "Innovation Challenge and Final Pitch" (later stages, not yet documented) |

### Calendar

| Date | Event |
|---|---|
| 1 Oct 2026 | Registration opened |
| 20 Oct 2026 | Data released |
| **21 Oct 2026 (today)** | Team A discovery |
| **17 Nov 2026 (Tue)** | **Submission deadline** |
| before 26 Nov 2026 | Results announced. Organisers may re-run the winner's repo to confirm it reproduces the file |

### What it is *not*

It is not a multi-object-tracking or game-state-reconstruction challenge. Tracking, tagging and homography are provided so we don't have to rebuild them. Improving or replacing them is **legal** but optional.

---

## 2. Rules and compliance: what can get us disqualified

### Hard rules (from RULES.md / OVERVIEW.md / FAQ.md)

| # | Rule | What it means for us |
|---|---|---|
| R1 | **Labels must come from an algorithm.** No hand annotation of the submission, and no hand-correcting algorithm output. | Every label in the CSV is produced by code in our repo. |
| R2 | **Small amounts of hand-labelled data for training/validation are fine.** | We *may* hand-label extra minutes as a validation set (§11). This is a major lever. |
| R3 | **No private GT, nor anything derived from it, beyond the public 5 minutes.** That includes "any other source of corrected possession data for this fixture". | **No third-party event data for this match** (Opta, WhoScored, match-event feeds). We avoid all fixture-specific external data unless organisers confirm in writing. |
| R4 | **The repo must regenerate *the same file*.** Approximately the same is not enough. | Determinism is a requirement: seeds, pinned environment, CPU-deterministic final run, and a sha256 check (§17). |
| R5 | **Everything must be accessible and inspectable**, and the tech doc must explain it. | No private in-house models or datasets. Public models are fine. |
| R6 | **Do not redistribute the data**, including in the public repo, and **do not publish derived data that would reconstruct it** (frame-level tracking exports, clipped video). | Caches, features, plots of raw frames and clips stay local. gitignore from day 1. |
| R7 | **LLMs are allowed in the pipeline, BUT** participants shall not upload or disclose the videos, datasets, confidential information, or *any extracts thereof*, to **any third-party hosted or cloud-based LLM**. | See below. |

### ⚠️ The LLM restriction applies to how we work, not only to the pipeline

Hosted coding assistants (ChatGPT, Claude, Gemini, Copilot chat) count as "third-party hosted LLMs". So:

- **Allowed:** using hosted assistants on the **public repository** (code, docs, the public 5-minute GT, which is published on GitHub) and on **our own code**.
- **Not allowed, pending clarification:** pasting rows of tracking data, Smart Tagging XML, homography values, video frames or screenshots, or data-bearing outputs (DataFrame heads, plots of frames) into a hosted assistant. We also must not let an assistant *read* the files in `data/` or our feature caches.
- **Grey zone; ask organisers:** sharing **aggregate** numbers computed from the data (e.g. "ball missing 42% in half 2", a spellF1 score) with a hosted assistant. Until they answer, treat it as allowed.
- **Safe alternative:** local open-weight LLMs running on our own machines are allowed for anything.
- **Side benefit of external data (§11):** public datasets from *other* matches (Sportec/IDSSE, Metrica samples) are not competition materials. Hosted assistants can help freely with loaders, features and models built on them, subject to those datasets' own licences. Only the step that runs on our gated match has to stay local.

**Working rule until clarified:** humans run code on the data locally. Hosted assistants only see code, error messages with no data in them, and the public repository. This document was produced under that rule: no gated data was opened.

### Submission hygiene (from SUBMISSION.md)

- Run `python evaluation/validate_submission.py <file>` **on the exact file being uploaded**. It applies the official checks, and a malformed file scores zero.
- Header exactly `frame,label`. No blank cells: write `X` to abstain. ~1.9 MB.
- Confirm the exact registered team name string; it sets the file names.

---

## 3. The data

> **Status:** not yet unpacked. Everything below comes from the repository docs and code. It is verified where marked ✅.

### 3.1 Assets

| | **tactical** (the reference) | **broadcast** (optional) |
|---|---|---|
| Role | **Row *i* of the submission is frame *i* of this video** | Not synchronised, own timeline, cuts and replays |
| Video | 199,319 frames, 25 fps, 1920×1080 | 164,488 frames |
| Tracking (ATD) | 199,319 records, **46 track slots** | 164,488 records, 51 slots |
| Homography | 199,319 rows, **100% valid** | 65.8% valid (122 invalid stretches, longest > 90 s) |
| Smart Tagging | 638 instances | none |
| Ball visible | 56.9% of all frames, 59.3% of graded frames | 50.5% |

Layout: `data/tactical/BAR-ATH_tactical{.mp4,_atd.xml,_atd.txt,_homography.csv,_smart_tagging.xml}` and `data/broadcast/…`. `games.asset_paths()` builds every path, and **`MTAH_DATA_DIR`** relocates the whole bundle.

### 3.2 Automatic Tracking Data (ATD)

- FIFA/EPTS format: metadata XML plus raw text. Raw line: `<frame_id>:<slot>;<slot>;…:<ball>`, each group `x,y,speed`, with `NaN` when missing. `kloppy==3.18.0` reads it (`metrica.load_tracking_epts`); `starter/baseline.py` parses it with the standard library alone.
- **Coordinates are normalised 0–1.** Multiply by **105.3 × 68.0 m** (`games.py`, measured from corrected tracking; the metadata says 105 × 68) before computing distances, because the pitch is not square.
- **No player identities.** 46 slots ("Track 1…46") for 22 players. Slots appear, vanish, swap and duplicate. Each slot has a team; the **first team in the XML is home** (Barcelona). About 20.5 objects are tracked per graded frame on average, sometimes more than 22.
- **Ball is NaN on 41% of graded frames**, disproportionately in the moments that matter (crowded boxes, aerial balls, tackles).
- Automatic and uncorrected: expect gaps, fragmented tracks and identity switches.

### 3.3 Smart Tagging (automatic, *not* ground truth)

SportsCode XML. `<start>`/`<end>` are seconds from tactical frame 0, so **`video_frame = round(s × 25)`** (verified by the organisers against both kickoffs).

| code | n | code | n |
|---|---|---|---|
| PLAYERS IN THE BOX | 97 | CREATING CHANCES | 30 |
| BALL IN FINAL THIRD | 93 | DEFENDING IN DEFENSIVE THIRD | 30 |
| BALL IN THE BOX | 72 | LONG BALL | 29 |
| PROGRESSION | 66 | ATTACKING TRANSITION | 24 |
| DEFENDING IN MIDDLE THIRD | 66 | DEFENSIVE TRANSITION | 24 |
| SET PIECES | 59 | BUILD UP | 22 |
| | | DEFENDING IN ATTACKING THIRD | 22 |
| | | GOALS | 4 |

- `Team`: `Barcelona` (314), **`Atletic Club`** (288, spelled like that in the data), **`N/A` (36), which includes every throw-in**.
- Set-piece `Type`: Throw-in 26 · Corner 12 · Goal Kick 10 · Free Kick 5 · Kick Off (After Goal) 4 · Kick Off (Start) 2.
- **Intervals are windows, not instants.** Kickoff tags open about 3.5 s before the real kickoff. They are phases, not possessions: one Build Up can cover part of a possession, or two.
- Codes are UPPER case, tag values Title Case, and tag columns Title Case (`Team`). Match case-insensitively.
- Why it is useful: going by the tag definitions (to be verified on the data), build-up, progression and creating-chances tags name the team **in** possession, defending tags name the team **out of** possession, and transition tags mark turnovers. Every set piece is a restart at the end of a dead-ball stretch.

### 3.4 Homography

One 3×3 matrix per frame, mapping **normalised pitch (0–1) to pixels**: `starter/load_homography.project(H[f], x, y)`. Check `valid` first (the matrix is NaN when invalid). Lower `reprojection_error` is better; the tactical median during play is 0.24. Its main use for us is **error analysis**: overlay tracking on video at the frames where we are wrong.

### 3.5 Frame alignment: the traps

| source | index | → submission row |
|---|---|---|
| submission | `0…199318` | n/a |
| ATD | `frame_id 1…199319` | **`frame_id − 1`** |
| Smart Tagging | seconds | **`round(s × 25)`** |
| homography | `frame 0…199318` | same as the submission row |

| segment | video frames | n | graded |
|---|---|---|---|
| before kickoff | 0–11,184 | 11,185 | no |
| **1st half** | **11,185–90,651** | 79,467 | **yes**, from the kickoff frame itself |
| halftime | 90,652–110,807 | 20,156 | no |
| **2nd half** | **110,808–190,197** | 79,390 | **yes** |
| after full time | 190,198–199,318 | 9,121 | no |

- ⚠️ **The 2nd half is graded from 110,808, but kickoff is at 113,742.** Those **2,934 graded frames are all `D`**. Writing `D` there is free credit, and writing a team there creates a 2-minute fake possession.
- ⚠️ `games.py` contains **per-half offsets around 1.7M** and an IdFrame range. Those describe the GT's internal counter, which we never see. **Do not use them on the ATD**; use `frame_id − 1` (per the `load_atd.py` docstring).
- ⚠️ `games.anchor_video_frame()` gives **11,186 and 113,741** for the kickoffs, each **off by one** from the documented 11,185 / 113,742 ✅ (verified by running it). Use the documented numbers.

---

## 4. What "possession" means here

- **Three states only:** `H`, `A`, `D`. There is no "contested" or "unknown" in the GT.
- **A possession is a maximal run of one team with the ball alive.** `H H D D H H` is **two** possessions. Dead ball is a stoppage, never a possession.
- **Loose or contested ball stays with the last team in possession.** Possession changes only when the opponent gains *controlled* possession. A touch, a deflection, or an aerial duel won without control does not count (per CHALLENGE.md).
- **Dead-ball ownership is not asked for.** When the ball is dead, the answer is `D`.
- **How the GT was made:** mechanically, from *corrected* tracking. A frame is `D` where the corrected tracking marks the ball dead; otherwise it takes the team that tracking names as owner. There is no smoothing or hand adjustment.
- **"If your reading of the definition disagrees with the GT, the GT is right."** It matters here, because the public GT contains possessions of **0.76 s (19 frames)** and **1.32 s (33 frames)**. Those look like "a simple touch" under the prose definition, but they count. So the GT's ownership is more touch-sensitive than the narrative suggests. **Action:** watch frames 15,346–15,365 and 15,766–15,799 on video once the data is unpacked, to learn what the GT treats as gaining control.

**The GT matches a published definition** (Research Lead). Link & Hoernig (2017)† define team possession as an unbroken sequence of individual possessions. It starts when a player can act on the ball and ends at the first individual possession by an opponent. A pass belongs to the passer, and dead-ball time belongs to nobody. That is our GT's logic almost exactly, so their definitions and timing results transfer.

Their model also opens an individual possession when the ball enters a player's **action space**, possibly before contact†. That is a plausible explanation for the 0.8 s and 1.3 s possessions: an automatic owner channel registers brief interventions that prose would call "a touch". **This is a hypothesis to confirm on video (checklist item 10), not a fact.** For scale: Link & Hoernig's own automatic individual-possession detection, the construct closest to our GT, reaches F = .83 at a 0.6 s tolerance, and only 52% of **human** loggers' entries fall within that tolerance†. Automatic boundaries are imperfect even on clean data, and **human timing is worse**, which matters for our silver set (§11.4).

**What this means for choosing external data:** the GT comes from a tracking **owner and ball-state channel**, "not from event data" (CHALLENGE.md). So external labels that come from a *per-frame tracking possession channel* are structurally closer to our GT than possession timelines reconstructed from *events* (§11).

---

## 5. The public ground truth, dissected

`evaluation/gt/BAR-ATH_possession_gt_public.csv` is full length (199,319 rows), with real labels only on frames 11,185–18,684 (7,500 frames, 5:00 of play). Reproduce the table with `python team_a/scripts/gt_dissect.py`.

| # | label | start | stop | dur (s) | t from KO (s) | | # | label | start | stop | dur (s) | t from KO (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | A | 11185 | 11351 | 6.6 | 0.0 | | 11 | A | 15365 | 15766 | 16.0 | 167.2 |
| 1 | H | 11351 | 11553 | 8.1 | 6.6 | | 12 | **H** | 15766 | 15799 | **1.3** | 183.2 |
| 2 | A | 11553 | 11624 | 2.8 | 14.7 | | 13 | A | 15799 | 15889 | 3.6 | 184.6 |
| 3 | H | 11624 | 12665 | 41.6 | 17.6 | | 14 | D | 15889 | 16400 | 20.4 | 188.2 |
| 4 | A | 12665 | 12851 | 7.4 | 59.2 | | 15 | A | 16400 | 17293 | 35.7 | 208.6 |
| 5 | D | 12851 | 12989 | 5.5 | 66.6 | | 16 | H | 17293 | 17380 | 3.5 | 244.3 |
| 6 | H | 12989 | 13704 | 28.6 | 72.2 | | 17 | D | 17380 | 17838 | 18.3 | 247.8 |
| 7 | A | 13704 | 13785 | 3.2 | 100.8 | | 18 | A | 17838 | 18027 | 7.6 | 266.1 |
| 8 | H | 13785 | 14846 | 42.4 | 104.0 | | 19 | D | 18027 | 18389 | 14.5 | 273.7 |
| 9 | A | 14846 | 15346 | 20.0 | 146.4 | | 20 | H | 18389 | 18685 | 11.8 | 288.2 |
| 10 | **H** | 15346 | 15365 | **0.8** | 166.4 | | | | | | | |

**What it tells us:**

| Fact | Value | Implication |
|---|---|---|
| Possessions | 17, **mean 14.2 s, median 7.6 s** (min 0.8, max 42.4) | Heavy-tailed. The mean hides that most possessions are short |
| Short possessions | **6 of 17 under 4 s**; 2 under 1.5 s | A ±2 s smoothing window (the floor) structurally cannot see them |
| Transition mix | 20 total: **12 open-play turnovers** (H↔A), 4 stoppages (→D), 4 restarts (D→) | Most of the work is detecting **turnovers in live play**, not stoppages |
| Dead-ball stretches | 4, lasting 5.5–20.4 s; 19.6% of frames | Stoppages are long and comparatively easy to see. Fake ones are the danger |
| Shares | H 46.1%, A 34.4%, D 19.6% | Barça dominated the opening |
| First label | `A` at 11,185 | Athletic kicked off the 1st half, so the 2nd-half kickoff team is probably Barça (verify) |

**Caveat:** this is the first 5 minutes of one match. Do not treat these rates (e.g. ~3.4 possessions per minute) as targets. The organisers deliberately withhold full-match counts so they cannot be tuned against.

---

## 6. How we are scored

`evaluation/possession_metrics.py` is the specification ("if this document and that file disagree, the file is right"). `evaluation/run_evaluation.py` is the exact official scorer. We reran it under Python 3.14 / numpy 2.5 / pandas 3.0 and it reproduced the published numbers exactly ✅.

### 6.1 spellF1, the ranking metric

1. **Fill abstentions:** within each graded half, every `X` is forward-filled with our previous non-X label (back-filled at the start of a half).
2. **Extract spells:** maximal runs of `H` or of `A`, per half. `D` runs are not spells, but they **cut** spells.
3. **Match:** compute IoU for every same-team overlapping (GT, predicted) pair. Then match greedily from the highest IoU down, **one-to-one**.
4. **F1** at IoU thresholds 0.3, 0.4, 0.5, 0.6 and 0.7, then **average**. Precision is matched/predicted spells and recall is matched/GT spells.

Consequences:
- **Every extra predicted spell is a false positive**, and every missed one a false negative. Count and boundaries matter; frame-level correctness inside a spell barely does.
- One flip inside a true possession **splits it in two**. Both halves then fall below the IoU threshold against the original, so we lose a TP and gain 2–3 FPs.
- A constant guess scores exactly 0. A **1-frame offset is free**; 3 frames late gives 0.98; 1 s late gives 0.65 (organisers' figures).
- **Noise:** differences under ~0.04 on the full match are noise. On the public 5 minutes the measured band is **0.23–0.33** (bootstrap, 1000 draws).

**Where the metric comes from** (Research Lead). Structurally, spellF1 is the **segmental F1@IoU** of video *temporal action segmentation*: segments are matched one-to-one above an overlap threshold. That field has studied our failure mode, **over-segmentation**, for years. Its main finding is that **explicit boundary detection beats smoothing**. ASRF (Ishikawa et al., WACV 2021) adds a boundary-regression branch that refines frame labels, and reports up to 16.1% gain in segmental F1†. The same paper notes that smoothing losses alone still over-segment†. A football stoppage paper (Lang et al. 2022) shows the same trade-off with a 3.64 s median filter†: short stoppages are missed, and brief play inside a stoppage splits it into one hit and one false alarm. This is our §7 dilemma, observed independently.

### 6.2 macroF1, the tie-break

Unweighted mean of per-class F1 over H, A and D on graded frames. A predicted `X` counts as a miss (FN) but adds no FP. Usable range is about [0.16, 1]. Differences under ~0.01 are noise.

### 6.3 What `X` really does

- On **spellF1**, `X` means "repeat my previous label". Writing that same label yourself gives an **identical** spellF1.
- On **macroF1**, `X` is a miss. Writing the carried label instead is a TP if right and FN+FP if wrong.
- ⇒ **`X` on graded frames can never improve the ranking metric.** It only shifts the tie-break. **Default policy: write a label on every graded frame**, and use `X` only on ungraded frames.
- At a transition, `X` is actively harmful: the old label bleeds across the hand-over.

### 6.4 Diagnostics the scorer gives us for free

`run_evaluation.py` writes `reports/<name>.json` and `reports/<name>_transitions.csv`. The latter lists every transition as **matched / missed / spurious with its video frame**, so we can seek the video to see what fooled us. Use `--out` to keep reports outside the repo, and `--bootstrap 1000` before believing any gap.

---

## 7. Metric sensitivity: which mistakes cost the most

We perturbed the public GT with one controlled defect at a time and scored it (`python team_a/scripts/metric_sensitivity.py`). It's 17 possessions, so read these as **orders of magnitude**, not exact costs. This is metric understanding, not model tuning.

| Defect injected into a perfect answer | spellF1 | macroF1 |
|---|---|---|
| none (perfect) | 1.000 | 1.000 |
| every boundary **3 frames** late (0.12 s) | 1.000 | 0.992 |
| every boundary **8 frames** late (0.32 s) | 0.953 | 0.978 |
| every boundary **25 frames** late (1 s) | 0.776 | 0.933 |
| every boundary **50 frames** late (2 s) | 0.588 | 0.875 |
| boundaries jittered N(0, 12 frames) | 0.928 | — |
| boundaries jittered N(0, 25 frames) | 0.838 | — |
| **5** spurious 10-frame opposite-team blips | 0.743 | — |
| **10** spurious blips | **0.578** | — |
| **20** spurious blips | **0.386** | — |
| **1 s false stoppage** inside every possession > 8 s (8 of them) | **0.610** | 0.968 |
| possessions < 1 s missed (absorbed into neighbour) | 0.912 | 0.998 |
| possessions < 2 s missed | 0.827 | 0.994 |
| possessions **< 4 s missed** | **0.560** | 0.967 |
| no dead ball at all (all 4 stoppages missed; previous team carried through) | 0.812 | 0.591 |
| 1 whole possession given to the wrong team | 0.921 | — |
| 3 whole possessions given to the wrong team | 0.762 | — |
| `X` for ±0.5 s around every true transition | 0.875 | 0.966 |
| `X` in the interior of every possession > 4 s | **1.000** | 0.569 |

The rows above inject several defects at once, so they mix the cost of an error with *how many* were injected. Injecting **exactly one** error at every eligible place gives the cost per error (`python team_a/scripts/per_error_cost.py`). One possession out of 17 is worth 0.059, which is the scale to read these against:

| One error of this kind | mean spellF1 cost | range | mean macroF1 cost (tie-break) | n tested |
|---|---|---|---|---|
| whole possession given to the wrong team | **0.080** | 0.030–0.125 | 0.040 | 17 |
| possession < 4 s missed (absorbed) | **0.070** | 0.030–0.091 | 0.007 | 6 |
| spurious 10-frame opposite-team blip | **0.063** | 0.056–0.089 | 0.001 | 200 |
| real stoppage missed | 0.046 | 0.024–0.059 | **0.069** | 4 |
| false 1 s stoppage inside a possession | 0.038 | 0.029–0.063 | 0.004 | 200 |
| one transition 1 s late | 0.011 | 0.000–0.088 | 0.003 | 20 |

**Every structural error costs about one possession (0.04–0.08); only timing is cheap.** So the priorities come from **how often each error occurs**, not from how much each one costs:

1. **Spurious flips: the most frequent error.** Proximity noise produces them constantly; the raw baseline makes 114 more possessions than the truth in 5 minutes. Each one costs a full possession (0.063). This is the first thing to eliminate.
2. **Missed short possessions: a third of all possessions.** Each costs 0.070. Majority-vote smoothing creates exactly this error, so smoothing harder trades error 1 for error 2.
3. **Restart team: the costliest single error (0.080)**, and an easy one to make at throw-ins, which Smart Tagging tags `N/A`.
4. **Stoppages, false and missed, cost about the same each** (0.038 vs 0.046). A false stoppage is slightly *cheaper* than a blip because `D` is not a spell, so it adds no false possession. The case for strict stoppage acceptance is **base rate**, not cost: the ball is missing on ~42% of frames, so there are far more chances to invent a stoppage than real stoppages to miss. Tune the stoppage threshold for **roughly equal numbers of false and missed stoppages** on validation data, not for maximum caution.
5. **Timing is cheap.** One transition 1 s late costs 0.011 on average, and ~0.3 s boundary precision is enough (0.95 with every boundary 8 frames late). Get the *events* right first; frame-exact timing is late-stage polish. This also means convention offsets under a second, e.g. in external training data (§11), are tolerable.

---

## 8. The baseline, dissected

`starter/baseline.py`: per frame, **nearest tracked player to the ball → that team**. **Ball missing → `D`.** Then a centred **majority vote** over ±w frames.

| baseline | window | **full-match** macroF1 | **full-match** spellF1 | public spellF1 [5–95% CI] | public poss (GT 17) | public mean dur (GT 14.2 s) |
|---|---|---|---|---|---|---|
| raw | 0 | 0.6532 | 0.0486 | 0.038 [0.019–0.060] | 131 | 2.0 s |
| smooth25 | ±1 s | **0.6752** | 0.1996 | 0.287 [0.196–0.385] | 36 | 7.6 s |
| **smooth50** | ±2 s | 0.6724 | **0.2433** ← floor | 0.326 [0.214–0.447] | 26 | 10.8 s |
| smooth125 | ±5 s | 0.6356 | 0.2242 | **0.424** [0.267–0.594] | 16 | 18.5 s |

What the confusion matrices show (public window, our run):

| | raw | smooth50 | smooth125 |
|---|---|---|---|
| **D recall** (dead frames called D) | 33.6% | 21.4% | **7.9%** |
| team accuracy where both agree the ball is alive | 77.8% | 85.8% | 88.5% |
| alive/dead F1 | 0.892 | 0.899 | 0.899 |
| transitions matched within ±1 s (of 20) | 11 | **2** | 3 |

**Lessons:**

- **Public order ≠ full-match order.** smooth125 wins on the public window and loses on the full match. That is the organisers' own demonstration of the overfitting trap, and the CIs overlap almost completely.
- **The floor matches only 2 of 20 transitions within ±1 s.** Its possessions overlap the truth only loosely.
- **Ball-missing is a poor dead-ball signal.** In the public window, ball missing covers just **33.6% of dead frames**, and **6.5% of live frames** are ball-missing and get mislabelled `D`. On the rest of the match, where the ball is missing **~42%** of the time, that rule produces false stoppages at scale, which is the expensive error from §7.
- **The full match is harder than the public window:** smooth50 drops from 0.33 to 0.24. Validating only on the public window will be optimistic.

### Proof of concept: a decoder alone is not a free win

We kept the baseline's exact signal and replaced majority vote with a 2-state (H/A) **Viterbi** decoder, using round a-priori parameters (switch prior ~10 s possessions, 75% emission accuracy, missing ball = no evidence). Two settings, no sweep (`python team_a/scripts/decoder_poc.py`):

| decoder | public spellF1 [CI] | poss (GT 17) |
|---|---|---|
| smooth50 (floor) | 0.326 [0.214–0.447] | 26 |
| Viterbi, per-frame evidence treated as independent | 0.088 [0.062–0.114] | **74** |
| Viterbi, evidence tempered to ~1 observation per second | 0.191 [0.070–0.303] | **6** |

**Takeaway:** nearest-player errors are **strongly correlated in time**. A defender standing next to the ball for half a second is not 12 independent pieces of evidence. With the evidence weighted naively, the decoder over-switches; tempered, it barely switches. **The right regime lies between the two settings, and nearest-player distance alone does not have the resolving power to find it reliably.** The decoder is necessary but not sufficient: we need **richer, better-calibrated evidence** (control, passes, shape, dead-ball cues) and an **external calibration target** to set the evidence-to-penalty ratio. This one experiment is the clearest argument for the architecture in §10.

**The literature has seen this exact pathology** (Research Lead). PathCRF (Kim et al., KDD 2026†) decodes possession paths from player trajectories. Its ablation finds that a **static** transition matrix always keeps a non-negligible chance of switching, so it over-detects events. Making the transition scores **depend on context** is what fixes it†:

| Decoding variant (same backbone)† | Event precision | Detected vs true events | Event F1 |
|---|---|---|---|
| per-step argmax (no structure) | 58.8% | 2,292 vs 1,831 | 65.3% |
| + Viterbi with hard transition masks | 69.5% | 2,033 vs 1,831 | 73.1% |
| static masked CRF | 68.6% | 2,135 vs 1,831 | 73.8% |
| **dynamic (context-dependent) masked CRF** | **73.2%** | **1,961 vs 1,831** | **75.7%** |

With context-dependent costs, staying in a state is cheap most of the time, and switching is cheap only when the situation supports it. That replaces our tempered-versus-untempered dilemma with a calibration problem: how strongly each cue lowers the cost of a switch. §10.2 turns this into our decoder design.

---

## 9. Key insights

1. **The score comes from possession structure.** Per-frame accuracy is already decent in the baselines. Teams that output clean, decisive segments will win.
2. **Every flip has to be earned, and its price should depend on context.** The system should switch possession only on positive evidence of control by the other team (reception, interception, dribble), never on proximity noise. The masked decoder in §10.2 enforces this structurally: a turnover is only possible through an opponent reception.
3. **Short possessions are real and frequent.** Detection has to be event-driven (a pass intercepted, a clean reception) rather than duration-driven.
4. **Treat a missing ball as missing data, not as a stoppage.** Carry the state, interpolate short gaps, and use collective player behaviour (team shape and motion) when the ball is gone.
5. **Dead ball is its own sub-problem, with strong and different cues:** ball outside the pitch, a stationary ball at a set-piece location, a collective drop in player speed, restart formations, and Smart Tagging `SET PIECES`. Published work detects stoppages from collective player movement alone, without the ball†. Our team-in-possession logic should run only *inside* live-ball periods.
6. **Smart Tagging is a free, noisy prior** on both the team (phase tags) and stoppages and restarts (set pieces). Fuse it as evidence; never copy its intervals as labels.
7. **Restarts are where the team label is easiest to get wrong and cheapest to fix.** Throw-ins are tagged `N/A`, so infer the restart team from geometry: who is at the ball, and the formations.
8. **The public window cannot rank our ideas.** We need our own validation data, public labelled matches from elsewhere to fit the bulk of the model (§11), and the discipline to use bootstrap CIs.
9. **Freebies:** `D` on the 2,934 pre-kickoff frames of the 2nd half; start each half with the kicking-off team; no `X` on graded frames.
10. **Reproducibility and compliance are pass/fail gates.** A brilliant model that cannot regenerate its file byte-for-byte, or that broke the data terms, scores nothing.

---

## 10. Solution space and recommended direction

### 10.1 Architecture: boundary-first, three layers plus a dead-ball track

The temporal-segmentation literature (§6.1) and our own PoC (§8) point the same way. **Boundaries should be detected as events and justified one by one. They should not emerge from smoothing frame labels.** Majority-vote and median filters are dropped from v2 onwards.

```
            ┌──────────────────────── Layer A: signals (per frame) ─────────────────────────┐
 ATD  ───►  │ ball x/y/vel/visibility · short-gap RTS/Kalman interpolation (≲1 s)          │
 Tags ───►  │ touch cues: ball-acceleration peak, direction/speed change in possession zone│
 Homog ──►  │ player-ball control: nearest-k per team, distance (zone-dependent radius)    │
 Public ─►  │ team shape and motion: centroid, spread, speeds, decelerations               │
 datasets   │ ball out of bounds · stationary ball at set-piece spot · Smart Tagging priors│
            └──────────────────────────────────────────────────────────────────────────────┘
                                │
            ┌──────── Layer B: evidence (two outputs) ───────────────────┐  ┌── Dead-ball track ──┐
            │ (i) state evidence per frame: H / A / D / "no evidence"   │◄─│ motion-based alive/ │
            │ (ii) candidate BOUNDARIES with scores: kick/release,      │  │ dead model + set-   │
            │      reception/gain by team, stoppage, restart (+ team)   │  │ piece geometry      │
            └────────────────────────────────────────────────────────────┘  └─────────────────────┘
                                │
            ┌─────────────── Layer C: masked, context-dependent decoder (§10.2) ──────────────┐
            │ hidden states: H-control, H-flight, A-control, A-flight, D                     │
            │ masks encode GT semantics · switch costs computed from Layer B evidence         │
            │ Viterbi · hard constraints: 2nd-half pre-KO = D, half starts with kicking team  │
            └─────────────────────────────────────────────────────────────────────────────────┘
                                │
                     submission CSV → validate → sha256
```

### 10.2 Decoder design: masked state machine with context-dependent switch costs

Proposed by the Research Lead and adopted here. This is **our synthesis, not a published model**. It borrows PathCRF's structure (masks plus context-dependent transitions†), not its network.

| Hidden state | Emits | Allowed next states | Cost of leaving is lowered by |
|---|---|---|---|
| **H-control** | `H` | H-control, H-flight, D | kick/release evidence (ball-acceleration peak, ball leaving the player) |
| **H-flight** (ball travelling or loose after an H touch) | `H` | H-flight, H-control, **A-control**, D | reception/gain evidence near a player, by team |
| **A-control** / **A-flight** | `A` | mirror of the above | mirror of the above |
| **D** | `D` | H-control, A-control | restart evidence: who is at the ball, set-piece geometry |

Why this fits our problem:

- **The masks are the GT's semantics.** A turnover can only happen as *flight → opponent control*, so a defender standing next to a ball that an attacker controls cannot flip the label. A loose ball is a flight state that emits the last team's label, so "a loose ball stays with the last team" comes for free. Open-play turnovers are 12 of the 20 public transitions, so this path carries most of the score.
- **Costs depend on context, not on a constant.** Each switch cost is a function of Layer B evidence (e.g. a logistic in reception strength). Staying is cheap by default, and switching becomes cheap only when a cue supports it. When the ball is missing, the cues vanish, so the state is carried automatically.
- **Calibration splits in two.** The mapping from evidence to cost is fitted on degraded external data (§11). Only **one global cost scale** and the decision thresholds are tuned on the in-convention data (silver set plus public window).
- **It fits the rules.** The model is tiny, runs on CPU, is deterministic, and every parameter can be explained, which serves R4 and R5.

Cautions, from the same paper† and our data:

- **Cross-provider transfer is poor.** A model trained on K League GPS data reached only 52.7% edge accuracy on Sportec, and 41.7% the other way round†. Anything fitted externally must be recalibrated on our convention.
- **PathCRF assumes 22 identified players; we have 46 fragmented, unidentified slots.** No published possession model is built for unidentified, fragmented tracks (Research Lead, RQ5). Two things soften this. Team-level possession only needs each slot's **team** label, which we have. And ordering-free team descriptors have precedent: SoccerTrack v2 spots ball actions from per-team centroid, dispersion, convex hull, speed, defensive and attacking lines, and a 6×3 player-density grid†. So use **per-frame team-level features** (nearest-k per team to the ball, team centroids, spreads, lines, speeds, density grids), not per-player temporal models.
- **PathCRF's 92.4% comes from a single test match**†, and its training labels were built from synchronised events plus touch points, **not** from the dataset's BallPossession code†. Read it as evidence for the structure, not as an accuracy we can expect.

### 10.3 Dead-ball design

| Step | Content | Source |
|---|---|---|
| **v1 rules (S1)** | Ball out of bounds (with margin) · stationary ball · collective speed drop · 2nd-half pre-kickoff = D | ours |
| **Motion model (S2)** | Gradient-boosted alive/dead classifier on **team-level** motion features: mean and top-k speeds per team, deceleration, spread, centroid, players near touchlines, corners and goal areas, ball out of bounds or stationary when visible. **Ball-missing is just one feature.** Multi-scale context windows (±0.4, 0.8, 2, 4, 20, 40, 80 s). Trained on degraded external data | Lang et al. 2022†: 92% frame accuracy, 0.80 stoppage F1 (IoU ≥ 0.5) without the ball; importance concentrated within ±4 s, past weighted over future |
| **Set-piece triggers (S2)** | At each candidate restart, check player and ball geometry: centre spot, corner, goal area, touchline. This confirms the stoppage and assigns the **restart team**: the team of the player at the ball, and for throw-ins the team of the player beyond the touchline | Vidal-Codina et al. 2022† rules; Mills et al. 2026†: on a tactical feed, kickoffs and corners F1 1.00, goal kicks 0.94, throw-ins 0.87 |
| **Smart Tagging** | `SET PIECES` windows as a prior that a stoppage exists nearby (windows open about 3.5 s early) | ours |
| **Stoppage fusion** | Motion, geometry, ball-out-of-bounds and Smart Tagging set-piece cues feed **one calibrated stoppage probability**. Threshold chosen by spellF1 on silver and degraded external data | Research Lead (memo v2), agreed ↓ |

**Why fusion rather than a hard two-cue rule.** Per error, false and missed stoppages cost about the same spellF1 (0.038 vs 0.046, §7). A hard rule requiring two independent cues would buy precision with recall for no cost reason. The memo's first version argued otherwise from §7 totals (8 injected errors versus 4); the Research Lead has since agreed. The calibrated probability handles the high base rate of ball gaps itself, because ball-missing is only one feature in it.

**Tie-break: lean towards recall when spellF1 can't separate two thresholds.** Per error, missing a real stoppage costs **0.069 macroF1**, while a false 1 s stoppage costs **0.004** (`per_error_cost.py`). The gap exists because real stoppages last 5–20 s. macroF1 only breaks exact spellF1 ties, so this is a preference among thresholds within spellF1 noise, not a target.

**Expect throw-ins to be the weak spot.** Published recall falls from 0.92 for kickoffs to 0.74 for throw-ins†. Throw-ins are also exactly where Smart Tagging gives no team (`N/A`), and a wrong restart team is the costliest single error (0.080, §7).

### 10.4 Evidence with and without the ball

- **Touch cues** that separate real touches from a ball merely passing near a player in 2D: a local **ball-acceleration peak** (Link & Hoernig: ≥ 4 m/s²†), and a **change in ball direction or speed inside the possession zone** (Vidal-Codina†).
- **Smoothing before the touch test (RQ6).** Link & Hoernig tuned the 4 m/s² threshold on acceleration from an RTS smoother, after removing ball jumps and discarding sections under 1 s. They give no smoother parameters, so **the threshold will not transfer as is**†. Vidal-Codina use a second-order Savitzky–Golay filter over 7 frames on noisy ball x–y†. Plan: smooth **within contiguous ball segments only, never across NaN gaps**. Compare RTS (constant-acceleration model) against Savitzky–Golay-7, then re-tune the threshold for touch-event recall at fixed precision on IDSSE. **PM addition:** tune on IDSSE *after* degradation (§11.3), with positional noise matched to our ATD. A threshold tuned on clean stadium tracking would fire too often on our noisier ball.
- **Starting radii:** Vidal-Codina use a 0.5 m / 1 m possession zone and a 1 m duel zone on stadium tracking†. Use these as starting values only.
- **Zone-dependent possession radius.** Make it wider in the final thirds and boxes, where automatic ball positions are least reliable (broadcast-derived ball RMSE 3.5–16.2 m across providers, with errors worst in attacking areas at the frame edges†). Vidal-Codina also recommend larger zones for lower-quality tracking†.
- **Short ball gaps (≲1 s; set the cut-off from our gap-length distribution):** RTS/Kalman interpolation, then run the touch cues.
- **Long gaps: do not impute a ball path and run touch detection on it.** That manufactures flips. Emit "no ball evidence", let the decoder carry the state, and add the team-shape cues: the attacking team spreads and advances, the defending team compacts and retreats.
- **Ball-free inference is an established research line.** PathCRF reports 92.4% team-possession frame accuracy from players alone†. Peral et al. report 82.1% possessor identification from trajectories, rising to 83.7% with team identity†. Both are optimistic for us: PathCRF's figure is from one test match†, and Peral et al. used **ground-truth** player trajectories as input†.

### 10.5 Options per layer

| Layer | Option | Effort | Expected impact | Status |
|---|---|---|---|---|
| **Dead ball** | v1 rules: out of bounds, stationary ball, speed drop | S | High | **v1** |
| | Motion-based GBM trained on degraded external data (§10.3) | M | **High** | **v2** |
| | Set-piece geometry triggers plus restart team | M | High (restart team is the costliest single error) | **v2** |
| | Smart Tagging `SET PIECES` / `GOALS` prior | S | Medium-High | v1–v2 |
| **Evidence** | Nearest-k per team with control criteria, zone-dependent radius | S | High | **v1** |
| | Kick and gain detectors (acceleration peak, direction/speed change) | S–M | **High.** This is how short real possessions get found | **v1** (cheap), refined in v2 |
| | Short-gap RTS; "no evidence" in long gaps | S | High on the 42% of frames with a missing ball | v1–v2 |
| | Team-shape and motion cues for ball-missing frames | M | Medium-High | v2 |
| | Smart Tagging phase team as a soft prior | S | Medium | v2 |
| **Decoder** | Hysteresis/FSM with kick and gain triggers | S | Medium-High | **v1** |
| | **Masked state machine with flight sub-states and context-dependent costs (§10.2)** | M | **High** | **v2 (recommended)** |
| | Static HMM/HSMM | M | Superseded: static costs over- or under-switch (§8) | fallback only |
| | Penalised change-point segmentation (PELT/DP) | M | Alternative | fallback only |
| **Stretch** | Port PathCRF's full network | L | Unknown: GPU training, poor cross-provider transfer† | only if WS4 is ahead |
| | Own ball detector on video (local) | L | Low-Medium: video-only possessor heads barely beat a threshold baseline (71.9% vs 70.6%†) | deprioritised |
| | Align broadcast ATD to tactical for extra ball observations | L | Medium | deprioritised |

### 10.6 Recommended roadmap

| Version | Content | Target |
|---|---|---|
| **v1: structured baseline** (by 1 Nov) | Freebies (§9.9) · missing ball ≠ D · dead-ball rules v1 · nearest-k with control criteria · hysteresis whose triggers use the **kick and gain cues from the start** (they are cheap) | Clearly above the floor (> 0.2433 + noise band). **Submitted to the form as insurance** |
| **v2: evidence + masked decoder** (by 8 Nov) | Masked, context-dependent decoder (§10.2) · motion-based dead-ball model plus set-piece triggers (§10.3) · both **fitted on degraded external data** and **calibrated on the silver set** · team-shape cues · Smart Tagging fusion · **no majority-vote or median smoothing** | Main competitive entry |
| **v3: hardening** (by 13 Nov) | Restart-team logic · boundary snapping to ball events · ablations with CIs · stretch items only if v2 is stable | Final |

### 10.7 What we will not do

- **No event synchronisation.** Smart Tagging has phases and set-piece windows, not on-ball events, so there is nothing to synchronise.
- **No large learned video models.** Little evidence of gain (§10.5), heavy compute, and they must stay strictly local (R7).
- **No full PathCRF port as the final model.** Copy its *structure*, not its GPU network.
- **No majority-vote or median smoothing from v2 onwards.** Boundaries come from events.

**Principle: few knobs, each with a football rationale.** Every parameter must be explainable in the tech doc and must not depend on the public window alone.

---

## 11. Validation strategy, with no leaderboard

We have 17 labelled possessions, a noise band of 0.23–0.33 on them, and no feedback before results. This needs a deliberate protocol.

### 11.1 Four tiers of labelled data, each with one job

| Tier | What | Size | Convention | Job |
|---|---|---|---|---|
| **External, degraded** | Public tracking datasets from *other* matches with possession and ball-status labels (§11.2) | ~1M frames† | **Not ours** | Fit the bulk of the model: dead-ball classifier, evidence-to-switch-cost mapping (possession codes only after the S1 audit, §11.2) |
| **Silver set** | Our hand-labelled minutes of this match | ≥ 30 min, ~100 possessions | Ours, via calibrated labellers | Final calibration of a handful of knobs; model selection |
| **Public GT** | The organisers' 5 minutes | 17 possessions | **Exact target** | Correctness, regression, labeller calibration |
| **Label-free checks** | The full match | 158,857 frames | n/a | Plausibility monitoring only; never optimised |

This is the Research Lead's main contribution. Fitting most parameters on external data removes the **scale** problem. Keeping only a few knobs for in-convention data handles the **convention** problem. It also turns our "missing calibration target" (§8) into an engineering task.

### 11.2 External datasets

**RULES.md explicitly permits "external data"**, and R3 bans only possession data *for this fixture*, so these are in bounds. Q7 (§15) asks organisers to confirm the details: committing weights, licences.

| Source | Offers | Fit | Caveats |
|---|---|---|---|
| **Sportec Open / IDSSE**: 7 Bundesliga 1 and 2 matches, 2022/23 (Bassek et al. 2025) | 25 Hz player and ball positions, events, and per-frame **BallPossession** (home or away, "player in control") and **BallStatus** (inactive when the referee interrupts play) codes†; 1,002,644 frames†; CC-BY 4.0†; loadable with `floodlight`. PathCRF trained on 5 of these matches† | **Closest in how labels are derived, if the audit passes.** Per-frame codes in a tracking feed resemble our GT, which also comes from a tracking owner and ball-state channel (§4) | **How the codes are produced is undocumented.** Older DFL/TRACAB work reportedly describes possession and in-game status as human-logged (source requested, RQ7), and PathCRF built its labels from events plus touch points instead of BallPossession†. A BallStatus that switches on the referee's interruption may not match our GT's dead-ball start. Hence the **S1 audit** below. Clean stadium tracking must be degraded. CC-BY requires attribution in our tech doc |
| **Metrica sample games 1–3** | Metrica's own synchronised tracking plus events (pass, carry, recovery, ball lost, ball out†); game 3 in the same EPTS format family as our ATD† | **Closest in provider and format.** Loader and feature testing; a third labelling convention for robustness checks | Possession would have to be **derived from events**, but our GT is explicitly "not from event data" (CHALLENGE.md). So it is **not a GT proxy** unless game 3 carries an owner or ball-state channel. The Research Lead agrees (memo v2). The data is public, so anyone can check this in S1, including with a hosted assistant. Anonymised; sample licence terms informal ("be responsible, acknowledge source")†; tracking likely corrected |

**IDSSE label audit (WS1, S1; go/no-go by 1 Nov).** The audit runs on public data only, so hosted assistants may help. It compares two label constructions: (a) IDSSE's own BallPossession and BallStatus codes, and (b) labels rebuilt from IDSSE events plus touch points (PathCRF's route). For each, measure the spell-length distribution, the share of spells under 1 s, switch timing relative to ball-acceleration peaks, and stoppage start relative to the ball leaving play. Compare the *shape* with the public GT (17 possessions, 6 under 4 s, 2 under 1.5 s; §5), not as a fit. **Go:** use the closer construction as boundary labels. **No-go:** use IDSSE only for the dead-ball model and for degradation tests.

Because a single transition 1 s late costs only ~0.011 (§7), convention offsets **under a second** are tolerable for fitting. Systematic differences, such as which touches count as possession, are not. They are what the final in-convention calibration is for.

### 11.3 Degrade-to-match protocol (WS1 + WS4, S1–S2)

1. **Common schema:** loaders for IDSSE and the Metrica samples that produce the same feature arrays as our ATD loader.
2. **Degrade** clean data to look like ours. Drop the ball using gap-length distributions and per-zone dropout rates computed **locally** from our ATD (the statistics stay local, §2). Fragment player tracks into unidentified team slots with appearances, disappearances and duplicates. Add positional noise. Published masking protocols cover parts of this: a camera module that hides off-screen players (Omidshafiei et al. 2022†) and uniform, agent-wise and camera-view missing patterns (MIDAS†). **None degrades the ball channel or fragments identities**, so our protocol is a composition that we must describe and justify in the tech doc.
3. **Fit** the dead-ball classifier and the evidence-to-switch-cost mapping on the degraded external matches.
4. **Calibrate** only the remaining few knobs, the global switch-cost scale and the decision thresholds, on the silver set plus public window.
5. **Report per source match, with bootstrap CIs.** Given PathCRF's cross-provider drop†, a model that wins only on IDSSE does not count.

Every external match also becomes a **ball-loss stress test**, which generalises the in-match stress test in §11.4.

### 11.4 Protocol on our own match

1. **Public GT = correctness and regression check only.** Every run reports spellF1 **with a bootstrap CI** (`--bootstrap 1000`) and possession count/duration. A change is never accepted on the public score alone.
2. **Build a "silver" validation set by hand-labelling extra minutes.** This is explicitly allowed for *validation/training* (R2).
   - **Calibrate the labellers first:** each labeller labels the public 5 minutes *blind*, then we compare against the GT and discuss the differences (especially the 0.8 s and 1.3 s possessions). This aligns us to the GT's mechanical definition, not our football intuition.
   - Label **transitions only** (frame plus new state), using a simple tool: video plus tracking overlay and keyboard shortcuts. About 20 transitions per 5 minutes. **Human timing is imprecise:** only 52% of human-logged entries fell within 0.6 s in Link & Hoernig's study†. So label with the tracking overlay, **snap each label to the nearest ball event** (acceleration peak, ball leaving play) within ±0.5 s, and rely on the silver set for **counts and structure** more than frame timing. Timing is cheap on spellF1 anyway (§7).
   - Target **≥ 30 extra minutes** (~100 possessions), stratified across both halves and including late-game periods with poor ball tracking. The noise band shrinks roughly with √(number of possessions).
   - Use it **for model selection and calibration only**, then hard-code the chosen parameters in config. The final pipeline then needs no hand labels to reproduce, and we never publish GT-like label files (see Q2 in §15).
3. **Stress test on realistic ball loss:** take ball-visibility masks from other 5-minute stretches of the match and apply them to the public window, simulating the 42% missing rate. A method that collapses under this will collapse on the full match.
4. **Label-free plausibility checks on the full match** (monitor, don't optimise): possession count and duration distribution, the number of `D` stretches against the 59 Smart Tagging set pieces, agreement of our team label with Smart Tagging phase teams, and home share.
5. **Visual review:** for every version, watch a sample of spurious and missed transitions (from `reports/*_transitions.csv`) with the homography overlay.
6. **Experiment log:** one row per experiment with commit, config hash, data tier, spellF1 [CI] per tier, poss/dur, **over- and under-segmentation counts and boundary offsets** (segment diagnostics, as in the segmentation literature), and notes. Decisions reference log rows.

### 11.5 Component sanity checks (necessary, not sufficient)

The public numbers here are tiny samples, so these are tripwires, not targets:

| Component | Check |
|---|---|
| Evidence (WS3) | Before decoding, candidate boundaries cover **≥ ~90% of the 12 public turnovers within ±1 s** |
| Dead ball (WS2) | On the public window: **≤ 1** false stoppage inside the 8 possessions over 8 s **and ≥ 3 of 4** real stoppages found at IoU ≥ 0.5 (balanced, per §10.3). Stoppage F1 at IoU ≥ 0.5 also reported on degraded external data |
| Decoder (WS4) | Possession count **within ±20%** of the truth on the public window (14–20) and on each external match |

**Acceptance rule for a change:** it must not hurt the silver set beyond noise, must not hurt the public window beyond noise, must not win on only one external source, must have a football rationale, and must not add an untestable knob. When in doubt, choose the simpler option.

---

## 12. Team structure and workstreams

Five workstreams for a 4–5 person team. With 3 people, merge WS1+WS4 and have the PM own the tech doc and submission. **Owners to be agreed at kickoff.**

| WS | Scope | First deliverable | Owner |
|---|---|---|---|
| **WS0: PM / integration** | Plan, decisions log, compliance and organiser comms (incl. Q7), Research Lead liaison, spot-check of decision-critical † sources (A1), tech doc incl. dataset attribution, form submission | Kickoff; organiser email sent | PM |
| **WS1: Data platform and reproducibility** | Local data setup, fast ATD parser into a cached numpy store (local, gitignored), **IDSSE (`floodlight`) and Metrica-sample loaders into the same schema**, **IDSSE label audit (go/no-go, §11.2)**, **degradation module** driven by local gap statistics, feature library, single `make_submission` entry point, pinned env, validation gate, clean-clone sha256 test | Baseline reproduced byte-for-byte; one feature-cache API for all three sources; audit verdict by 1 Nov | TBD |
| **WS2: Dead-ball detection** | v1 rules → motion-based GBM on team-level features (§10.3) → set-piece geometry triggers and restart team (incl. throw-ins) · 2nd-half pre-kickoff · Smart Tagging set pieces · one calibrated stoppage probability, threshold by spellF1 (leaning towards recall when tied) | Dead-ball v1 with stoppage precision/recall on the public set; v2 stoppage F1 on degraded external data | TBD |
| **WS3: Possession evidence** | Kick and gain detectors · nearest-k control criteria with zone-dependent radius · short-gap RTS and the long-gap "no evidence" policy · team-shape cues for ball-missing frames · Smart Tagging phase priors · **candidate boundaries with scores** | Candidate boundaries covering ≥ ~90% of public turnovers within ±1 s (§11.5) | TBD |
| **WS4: Decoder and evaluation** | Masked context-dependent decoder (§10.2) · X policy · metric experiments, bootstrap, segment diagnostics · silver set and labelling protocol · degrade-to-match evaluation per source · error-analysis tooling | Silver set (≥ 30 min); hysteresis v1; masked decoder v2 | TBD |
| **Research Lead (advisor)** | Literature support, answers to the follow-up questions (§15), source pages for the † figures we depend on | Answers before S2 starts (2 Nov) | Research Lead |

**Rituals:** a 15-minute daily async stand-up (yesterday / today / blockers / any new experiment-log rows) and two 45-minute syncs per week (Mon and Thu) to review the log and take decisions.

---

## 13. Plan and milestones

| Sprint | Dates | Goals | Exit criteria |
|---|---|---|---|
| **S0: Discovery and setup** | Wed 21 – Fri 23 Oct | This doc · kickoff and owners · organiser questions sent · all members enrolled · data unpacked outside OneDrive · env pinned · team repo created (private for now) | `starter/baseline.py` output **identical** to the committed `baseline_*.csv` on two machines |
| **S1: Foundations and v1** | Sat 24 Oct – Sun 1 Nov | Feature cache · full-match exploration (ball gaps, slot lifetimes, out-of-bounds, speeds, attack directions) · **IDSSE and Metrica-sample loaders plus degradation module** · labeller calibration on public 5 minutes · v1 pipeline with kick and gain triggers · IDSSE label audit (go/no-go) · spot-check of decision-critical † sources (A1) | **v1 submitted to the form** (validated, sha256 logged); Q7 answered or fallback chosen |
| **S2: Evidence and decoder** | Mon 2 – Sun 8 Nov | Silver set ≥ 30 min (by 4 Nov) · candidate boundaries · shape features · motion-based dead-ball GBM and set-piece triggers · **masked context-dependent decoder**, fitted on degraded external data and calibrated on silver | v2 beats v1 on silver beyond noise, and does not win on only one external source |
| **S3: Consolidation** | Mon 9 – Fri 13 Nov | Ablations with CIs · ball-loss stress test · restart-team logic · tech doc draft · **code freeze Fri 13 Nov EOD** | Final candidate chosen and logged |
| **S4: Release** | Sat 14 – Mon 16 Nov | Clean-clone reproduction on a fresh machine (sha256 match) · data-leak audit of repo · repo made public · tech doc final · **final form submission Mon 16 Nov** | Form response confirmed; files named `<team_name>.*` |
| Buffer | Tue 17 Nov | Deadline day: emergencies only | n/a |

---

## 14. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | **Breach of the LLM/data restriction** (data or extracts shared with a hosted assistant) | Medium | **Critical** (T&C breach / DQ) | Working rule in §2 · written clarification · local LLMs for anything that touches data | PM |
| 2 | **Overfitting to the public window** (17 possessions, band 0.23–0.33) | High | High | External data for bulk fitting · silver set · CIs · acceptance rule · few knobs | WS4 |
| 3 | **Public window easier than the match** (ball missing 12% vs 42%) | Certain | High | Ball-loss stress tests (in-match and on degraded external matches) · shape features · gap interpolation | WS3/WS4 |
| 4 | **Non-reproducible file** (randomness, env drift, threading, paths) | Medium | **Critical** | Seeds · pinned env (Python 3.11 plus lockfile) · CPU-only final run · sha256 gate · clean-clone test | WS1 |
| 5 | **Data leak via the public repo** (data, caches, frame-level exports, clips, label files) | Medium | High | gitignore from day 1 · pre-commit size/path guard · audit before going public | WS1 |
| 6 | **Use of forbidden external data** (event data for this fixture) | Low | **Critical** | Blanket ban unless organisers confirm | PM |
| 7 | **Submission logistics** (Google account, wrong file, wrong name, late) | Low | Critical | Early v1 dry run · checklist · submit D-1 | PM |
| 8 | **Scope creep into computer vision** (own detector or tracker) | Medium | Medium | Stretch only after v2 is stable; timeboxed | PM |
| 9 | **GT semantics mismatch** (prose "controlled" vs a touch-sensitive mechanical GT) | High | Medium | Labeller calibration · study the short spells on video | WS4 |
| 10 | **Environment friction:** repo inside OneDrive, a path containing `&` and spaces, multi-GB video syncing | High | Medium | Data in a non-synced folder via `MTAH_DATA_DIR` · venvs outside OneDrive · always quote paths | WS1 |
| 11 | **Team eligibility** (< 3 members, members not enrolled) | Low | High | Confirm the roster and enrolment at kickoff | PM |
| 12 | **Literature figures** (†) drive a design or data decision and turn out wrong or misattributed | Low | Medium | Research Lead re-verified most with locations (§18.4) · independent spot-check of the two decision-critical sources (A1) · ⚠ rows kept out of decisions and the tech doc | PM / Research Lead |
| 13 | **External labels follow a different convention** (DFL possession/ball-status vs Metrica's corrected tracking; event-derived vs tracking-derived) | High | Medium | Fit bulk parameters externally, calibrate the last knobs in-convention (§11.3) · IDSSE label audit with go/no-go (§11.2) | WS1 / WS4 |
| 14 | **Poor cross-provider transfer** (PathCRF: 52.7% / 41.7%†) | High | Medium | Team-level aggregate features · degradation module · per-source reporting · "wins on one source" doesn't count | WS1 / WS4 |
| 15 | **Q7 answered "no"**, or weights/licences complicate reproduction | Low | Medium | Fallback: rules plus silver-set calibration only (the v1/v2 design works without external data, just with less calibration data) · CC-BY attribution in the tech doc | PM |

---

## 15. Open questions

### For the organisers

T&C questions go by email to hackathon.talentarena@mobileworldcapital.com. Technical ones go as a GitHub issue, which is public, so keep them strategy-neutral.

| # | Question | Why it matters |
|---|---|---|
| Q1 | Does the hosted-LLM ban cover (a) coding assistants that see only our code and **aggregate** statistics, and (b) enterprise LLM deployments with zero data retention? | Defines how we can work day to day (§2) |
| Q2 | Hand-labelled validation data: is ~30–60 minutes "small"? If a model is trained on it, may the label file go in our public repo for reproducibility, or should it stay private? | Silver-set design (§11) |
| Q3 | Does every team member need to enrol and accept the T&Cs individually to access the data? | Eligibility and compliance |
| Q4 | What are the "Innovation Challenge" and "Final Pitch": dates, format, how Phase 1 feeds into them? | Planning beyond 17 Nov |
| Q5 | Is any fixture-specific public information (e.g. goal times from match reports) acceptable, or does R3 cover it? | We assume **not allowed** |
| Q6 | Must the repo be public only at submission time, or earlier? | Repo strategy |
| Q7 | RULES.md allows external data and public pre-trained models. Please confirm: (a) public datasets from **other** matches (Sportec/IDSSE, Metrica sample games) may be used to train and calibrate; (b) **committing trained weights** to our repo satisfies "the repository regenerates the same file", or must the reproduction command retrain from scratch? | External-data strategy (§11.2); needed before S2 |

### For the Research Lead (follow-up on the literature memo)

RQ1–RQ6 were answered in the Research Lead's memo v2 (22 Oct); the doc has been updated accordingly. RQ7–RQ8 are still open. The advisor isn't reachable as a live session, so the PM forwards them. **Answers are needed before the IDSSE audit verdict (1 Nov).**

| # | Answer (memo v2) | Status |
|---|---|---|
| RQ1 | Agrees per-error costs are equal; replaces the hard two-cue rule with calibrated fusion and a spellF1-chosen threshold, leaning towards recall on macroF1 | **Closed** (§10.3) |
| RQ2 | Production of IDSSE codes undocumented; BallStatus inactive when the referee interrupts play; reportedly human-logged in older DFL/TRACAB work → audit with go/no-go | **Closed** (§11.2); source for "human-logged" → RQ7 |
| RQ3 | Agrees: Metrica event-derived possession is not a GT proxy unless game 3 has an owner or ball-state channel | **Closed** (§11.2); channel check in S1 |
| RQ4 | Locations supplied for all relied-upon figures; most re-verified | **Closed** (§18.4); spot-check under A1 |
| RQ5 | No published model for unidentified, fragmented tracks; team label suffices; SoccerTrack v2 ordering-free team features | **Closed** (§10.2) |
| RQ6 | RTS (Link & Hoernig) or Savitzky–Golay-7 (Vidal-Codina), within contiguous segments only; re-tune the threshold. Masking protocols exist for players, none for the ball or identity fragmentation | **Closed** (§10.4, §11.3) |

**Still open:**

| # | Question | Why it matters |
|---|---|---|
| RQ7 | Which source says DFL/TRACAB possession and in-game status are human-logged? | Weighs the IDSSE audit; needed if the tech doc repeats the claim |
| RQ8 | The Omidshafiei et al. link (`pmc.ncbi.nlm.nih.gov/articles/9126960`) looks malformed, probably missing the "PMC" prefix. Could you also confirm the MIDAS missing-pattern list from the paper itself, and the Peral et al. VISAPP figure? | All three are cited in §10.5 / §11.3 and marked ⚠ in §18.4 |

#### Original questions (for reference)

| # | Question | Why it matters |
|---|---|---|
| RQ1 | The memo justifies two-cue stoppage acceptance by asymmetric cost (0.39 vs 0.19). Those are §7 totals for 8 vs 4 injected errors; **per event the costs are 0.038 vs 0.046**. Do you still recommend the rule on base-rate grounds, and would you tune it for balanced false and missed stoppages? | Dead-ball acceptance logic (§10.3) |
| RQ2 | Are IDSSE's per-frame possession and ball-status codes produced by DFL's algorithm or by manual annotation? How do their rules compare with our GT: when a turnover registers, and whether dead ball starts at line-crossing or at the whistle? | Whether IDSSE labels are fit for calibration (§11.2) |
| RQ3 | Our GT is derived from a tracking owner channel, "not from event data". Why rank Metrica event-derived possession as the closest analogue? Does Metrica sample game 3's EPTS export carry any ball-state or owner channel? | Choice of external source (§11.2) |
| RQ4 | Please give page/table references for the † figures we will rely on: PathCRF ablation and transfer numbers; Lang et al. stoppage F1, context windows and per-type recall; the Link & Hoernig 4 m/s² threshold; IDSSE frame count, labels and licence; Mills et al. set-piece F1. | Action A1 |
| RQ5 | Is there published work on possession or stoppage inference from **unidentified, fragmented** tracks (our 46 slots), rather than 22 identified players? | Feature design (§10.2 cautions) |
| RQ6 | On noisy automatic 25 fps ball positions, what smoothing should precede the acceleration-peak test? Is there a published degradation protocol (dropout, fragmentation, identity switches, noise levels) we can cite for §11.3? | Touch cues (§10.4); degradation module |

### For the team (decide at kickoff)

- Roster, owners, and the exact registered **team name** (it sets the file names).
- Hardware: who has a GPU, and is any video work worth it?
- Language/stack: Python 3.11 plus numpy/pandas/scikit-learn/LightGBM? Any objections?
- How much labelling time can each member commit for the silver set? Target ~2 hours each.

---

## 16. Day-1 data unpacking checklist

> **Run locally by a team member.** Under the working rule in §2, no hosted assistant reads the files or their contents.

1. ☐ Every member enrolled, T&Cs read and accepted.
2. ☐ Unpack into a folder **outside OneDrive** (e.g. `~/mtah2027-data/`), then `export MTAH_DATA_DIR=~/mtah2027-data`. Keep the folder names exactly as shipped (`tactical/`, `broadcast/`).
3. ☐ Check the file list and sizes against §3.1. Record sha256 checksums of the bundle in our (private) notes.
4. ☐ `python starter/load_atd.py`: expect "OK — one record per video frame, numbered from 1".
5. ☐ `python starter/load_smart_tagging.py`: expect the time-base check OK on both kickoffs.
6. ☐ `python starter/load_homography.py`: tactical 100% valid, broadcast 65.8%.
7. ☐ `python starter/baseline.py --out /tmp/baseline_check`, then `diff` each file against `evaluation/results/baseline_*.csv`. **They must be identical.** This is our first reproducibility proof.
8. ☐ Inspect `BAR-ATH_tactical_atd.xml`: list every data channel. **Is there a ball z/height, ball-state or ball-owner channel?** If so, it changes the strategy.
9. ☐ First local exploration (results stay local; share only conclusions in team channels): ball NaN rate per half and per minute · gap-length distribution · slot lifetimes and duplicates · ball coordinates outside [0,1] · player speed distribution in live vs dead periods · team attack direction per half · 2nd-half kickoff team · **ball gap-length distribution and per-zone dropout rates**, which drive the degradation module (§11.3). These statistics stay local.
10. ☐ Watch on video: the 0.8 s and 1.3 s possessions (frames 15,346 and 15,766), the 4 public stoppages (12,851; 15,889; 17,380; 18,027), and the 2nd-half kickoff at 113,742.
11. ☐ Build the local feature cache (npz/parquet) **inside `MTAH_DATA_DIR`**, never in the repo.

---

## 17. Engineering conventions

- **Two repos:** this one, the organisers' reference, stays untouched apart from `team_a/`. Our **team repo** holds the solution and becomes public at submission. The scorer is MIT-licensed, so vendoring `evaluation/` for tests is fine.
- **Proposed layout:**
  ```
  src/teama/{io.py, features/, dead_ball.py, evidence.py, decode.py, pipeline.py}
  configs/final.yaml            # every parameter, with a comment saying why
  scripts/make_submission.py    # data → CSV → validate → sha256, one command
  tests/                        # metric unit tests, alignment tests, determinism test
  docs/technical_document.md
  ```
- **One command** regenerates the submission: `python scripts/make_submission.py --config configs/final.yaml --out submissions/<team_name>.csv`. It runs the validator and prints the sha256.
- **Determinism:** fixed seeds, sorted iteration, CPU-only final run, `OMP_NUM_THREADS=1` for the final build, pinned versions (Python 3.11 plus a lockfile). Test: two runs on two machines produce the same sha256.
- **Gate on every merge:** validator passes · public score with CI · metric unit tests · determinism test.
- **Never commit:** `data/`, caches, features, submissions, reports, videos/clips/frame images, hand-label files (pending Q2). Add a pre-commit guard for files over 1 MB and for those paths.
- **Paths:** this checkout sits under a OneDrive path containing `&` and spaces. Quote every path in shell scripts, and keep venvs and data outside OneDrive.

---

## 18. Appendix

### 18.1 Gotchas and inconsistencies found in the repository

| # | Finding | Severity | Handling |
|---|---|---|---|
| 1 | `games.anchor_video_frame()` gives 11,186 / 113,741 for the kickoffs. The docs say 11,185 / 113,742 | Low | Use the documented values |
| 2 | `games.py` per-half offsets (≈1.7M) and the public GT meta JSON describe the GT's internal IdFrame counter, not the ATD `frame_id` | Medium (trap) | ATD: `video_frame = frame_id − 1` |
| 3 | `possession_metrics.macro_f1` docstring calls it "the metric the scoreboard ranks on". Stale: ranking is on spellF1 | Low | Ignore; `RANK_METRIC = "spell_f1_mean"` |
| 4 | `run_evaluation.py --bootstrap` help mentions only macro-F1, but it also drives the spellF1 interval | Low | n/a |
| 5 | Smart Tagging team value is **`Atletic Club`** (sic) | Medium (silent mismatch) | Map exact strings and assert full coverage |
| 6 | The prose definition ("a simple touch does not count") vs GT possessions of 0.76 s and 1.32 s | Medium | GT wins (§4) |
| 7 | The public window is unrepresentative of ball visibility (11.8% vs ~42% missing) | High | Stress tests (§11.3, §11.4) |
| 8 | Scorer stated as tested on Python 3.8/3.11. We confirmed identical output on 3.14 / numpy 2.5 / pandas 3.0 | Info | Still pin 3.11 for the team |

### 18.2 Command cheat sheet

```bash
pip install -r requirements.txt                                       # scorer: numpy + pandas
pip install -r requirements-starter.txt                               # notebooks: kloppy 3.18.0, matplotlib, notebook
python evaluation/run_evaluation.py --out /tmp/eval --bootstrap 1000  # score evaluation/results/*.csv on public GT
python evaluation/validate_submission.py path/to/file.csv             # ALWAYS, on the exact file uploaded
python starter/baseline.py --out /tmp/baselines                       # rebuild the 4 baselines (needs data)
python starter/make_dummy_submission.py --out /tmp/dummies            # trivial valid files
python team_a/scripts/gt_dissect.py                                   # §5 table
python team_a/scripts/metric_sensitivity.py                           # §7 table (many errors at once)
python team_a/scripts/per_error_cost.py                               # §7 table (cost of one error)
python team_a/scripts/decoder_poc.py                                  # §8 decoder experiment
```

Starter notebooks: `starter/01_smart_tagging.ipynb` → `02_tracking_atd.ipynb` → `03_first_submission.ipynb`. They need data, and kloppy for the first two.

### 18.3 Glossary

| Term | Meaning |
|---|---|
| **ATD** | Automatic Tracking Data: Metrica's computer-vision output, uncorrected |
| **Spell / possession** | Maximal run of `H` or of `A` within a half |
| **Segment** | Maximal run of any single label (H, A or D) |
| **IoU** | Intersection-over-union of two time intervals |
| **spellF1** | Mean over IoU 0.3–0.7 of the F1 of one-to-one possession matching. The ranking metric |
| **macroF1** | Mean per-class frame F1 over H, A, D. The tie-break |
| **Silver set** | Our own hand-labelled validation minutes (for validation only, not submission) |
| **HMM / HSMM** | (Hidden semi-) Markov model: a probabilistic state model, decoded with Viterbi |
| **Floor** | baseline_smooth50, full-match spellF1 0.2433 |
| **Flight sub-state** | Decoder state for a ball travelling or loose after a team's touch; emits that team's label (§10.2) |
| **Degrade-to-match** | Making clean external tracking look like our ATD (ball dropout, slot fragmentation, noise) before fitting (§11.3) |
| **†** | Literature figure via the Research Lead's memo; source location and verification status in §18.4 |
| **⚠** | Literature item not re-verified, or with no source; kept out of decisions and the tech doc until checked |

### 18.4 Literature register (from the Research Lead's memo, v2)

**Action A1 (owner: PM, due before S2).** The Research Lead re-verified most figures against the source text on 21 Oct and gave a location for each (memo v2, appendix). A1 now covers two things:

- An **independent spot-check of the two decision-critical sources**: Bassek et al. *Data Records* (IDSSE labels and licence) and PathCRF *Table 2* (the decoding ablation). This takes about 30 minutes for one team member, using public papers only.
- Keeping rows marked ⚠ **out of decisions and out of the tech doc** until they are checked.

| Source | Figures used here | Location (per Research Lead) | Status |
|---|---|---|---|
| Link & Hoernig 2017, *Individual ball possession in soccer*, PLOS ONE 12:e0179953 ([PMC5503225](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225)) | Possession definitions; action space (§4) | §2, Fig. 2 | Re-verified by RL |
| | RTS smoothing, jump removal, sections < 1 s dropped; kick = local ball-acceleration max ≥ 4 m/s² (§10.4) | §3.1; §3.2, Fig. 4 caption | Re-verified by RL |
| | Individual-possession detection F = .83 (timeline .87) at 0.6 s tolerance; human loggers 52% within 0.6 s (§4, §11.4) | Table 1, §4.2 | Re-verified by RL |
| Vidal-Codina et al. 2022, Sports Eng. 25:18 ([arXiv 2202.00804](https://ar5iv.arxiv.org/html/2202.00804)) | Savitzky–Golay order 2 / 7 frames; gain needs a change in ball direction or speed; zones 0.5 m / 1 m, duel 1 m; wider zones and per-provider tuning for weaker tracking (§10.3, §10.4) | §2.3.1, §2.3.3; §3; §3.1, Fig. 7a; §4 | Re-verified by RL |
| Kim et al., PathCRF, KDD 2026 ([arXiv 2602.12080](https://arxiv.org/pdf/2602.12080)) | Decoding ablation (§8) | §3.4, Table 2 | Re-verified by RL; **spot-check (A1)** |
| | 92.40% team-possession accuracy; share 62.64% vs 62.13% (§10.2, §10.4) | §4.2 | Re-verified by RL; **single test match** |
| | Cross-provider edge accuracy 52.71% / 41.65% (§10.2, §14) | Appendix B, Table 6 | Re-verified by RL |
| | Trained on 5 Sportec matches; labels from events plus touch points, not BallPossession (§10.2, §11.2) | §3.1, Table 1 | Re-verified by RL |
| Lang et al. 2022, Sci. Rep. 12:16291 ([s41598-022-19948-1](https://www.nature.com/articles/s41598-022-19948-1)) | 92% frame accuracy; 0.80 stoppage F1 (IoU ≥ 0.5, > 2 s); context ±0.4–80 s; 3.64 s median-filter failure modes; recall 0.92 kickoff → 0.74 throw-in; 77% / 81% of starts/ends within ±2 s (§6.1, §10.3) | Table 1; Methods; Results; Discussion; Table 2; Fig. 2 | Re-verified by RL |
| Mills et al. 2026, Sports Eng. 29:15 ([s12283-026-00549-4](https://link.springer.com/article/10.1007/s12283-026-00549-4)) | Set-piece F1 on tactical tracking (kickoff/corner 1.00, goal kick 0.94, throw-in 0.87, free kick > 0.85); ball RMSE 3.5–16.2 m (§10.3, §10.4) | §3.2, Table 2; §4.1, Table 1, Fig. 3 | Re-verified by RL |
| Peral et al., *Multi-Modal Soccer Scene Analysis with Masked Pre-Training* ([arXiv 2512.19528](https://arxiv.org/pdf/2512.19528)) | Possessor 82.12% → 83.66% with team; inputs are **ground-truth** trajectories (§10.4) | Tables 1–2 | Re-verified by RL |
| Bassek et al. 2025, Sci. Data 12:195, Sportec Open / IDSSE ([PMC11787359](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11787359/)) | 7 matches; 1,002,644 frames; CC-BY 4.0; BallPossession and BallStatus definitions (§11.2) | Data Records; Data Records → Position data; Methods → Position data | Re-verified by RL; **spot-check (A1)** |
| Scott et al. 2026, SoccerTrack v2 ([arXiv 2508.01802](https://arxiv.org/html/2508.01802)) | Ordering-free team descriptors (§10.2) | §4.9 | Re-verified by RL (section text) |
| Ishikawa et al. 2021, ASRF, WACV ([arXiv 2007.06866](https://arxiv.org/abs/2007.06866)) | +16.1% segmental F1; smoothing still over-segments (§6.1) | Abstract; §1 | Re-verified by RL from abstract and introduction only. Used for direction, not numbers |
| Peral et al., VISAPP 2025 ([scitepress](https://scitepress.org/publishedPapers/2025/133177/pdf/index.html)) | Video-only possessor 71.9% vs 70.6% (§10.5) | n/a | ⚠ **Not re-verified** |
| Omidshafiei et al. 2022, Sci. Rep. ([link as cited](https://pmc.ncbi.nlm.nih.gov/articles/9126960), likely missing the "PMC" prefix) | Camera-module masking of off-screen players (§11.3) | Abstract; Fig. 1 | ⚠ Abstract-level only; link to fix (RQ8) |
| Choi et al., MIDAS, ECML PKDD 2025 ([arXiv 2408.10878](https://arxiv.org/abs/2408.10878v4)) | Uniform, agent-wise and camera-view missing patterns (§11.3) | Fig. 1; experiments | ⚠ From a secondary summary; check before citing in tech doc |
| *"Older DFL/TRACAB work"* describing possession and in-game status as human-logged (§11.2) | Caveat on IDSSE labels | none given | ⚠ **No source cited** (RQ7) |
| Metrica Sports sample data ([GitHub](https://github.com/metrica-sports/sample-data)) | Licence terms; whether game 3 has an owner/ball-state channel (§11.2) | README; game 3 metadata | To check in S1 (public data, quick) |

**Points resolved with the Research Lead (memo v1 → v2):**

- *Stoppage acceptance:* the hard two-cue rule was justified from §7 totals. It is now **calibrated fusion** with a spellF1-chosen threshold (§10.3). Our per-error macroF1 check (0.069 vs 0.004) supports the memo's recall lean, but only as a tie-break.
- *Metrica event-derived possession as "closest analogue":* withdrawn. It is now "not a GT proxy unless game 3 carries an owner or ball-state channel" (§11.2).
- *IDSSE codes:* how they are produced is undocumented, so they go through an **S1 audit with go/no-go** (§11.2).

### 18.5 Change log

| Version | Date | Change |
|---|---|---|
| v1.0 | 21 Oct 2026 | Initial discovery: repository, challenge, data, metric, public GT, baselines, plan |
| v1.1 | 21 Oct 2026 | Merged the Research Lead's literature memo: boundary-first architecture, masked context-dependent decoder (§10.2), motion-based dead-ball design (§10.3), external data tiers and degrade-to-match protocol (§11), Q7 and RQ1–RQ6 (§15), risks 12–15, literature register (§18.4). **Corrected §7**: added the cost of a single error and re-ranked priorities by frequency (new script `per_error_cost.py`) |
| v1.2 | 22 Oct 2026 | Merged memo v2 (answers to RQ1–RQ6): calibrated stoppage fusion replaces the two-cue rule (§10.3), with per-error macroF1 added to `per_error_cost.py`; IDSSE label audit with go/no-go (§11.2); smoothing and radius guidance for touch cues (§10.4); team-level features for fragmented tracks (§10.2); human-timing caveat for the silver set (§11.4); degradation precedents (§11.3); register rebuilt with source locations (§18.4); RQ7–RQ8 open |
