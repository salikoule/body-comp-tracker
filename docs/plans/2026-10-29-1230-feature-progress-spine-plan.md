---
title: Progress spine and journey
date: 2026-10-29
type: feature
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

Objective: On Progress, a signed-in athlete can see the whole plan as one week story and tell, for each logged week, whether the body hit the plan.

Means: One multi-grid ECharts spine plus a side journey chart on Progress (KTD1).

Product authority: Progress page only. Tracker, check-in, and food logging stay as they are.

Open blockers: None.

Product Contract preservation: deferred hit/macro questions resolved as KTD3–KTD5; R-IDs unchanged.

## Product Contract

### Summary

Progress becomes one shared-week spine (weight, body fat, stacked macros) with phase bands and a side journey plot. Logged weeks score hit or miss against the plan. Weeks after now stay a faded forecast. Issued macros stand in for calories.

### Problem Frame

Three disconnected charts hide whether a calorie or macro change moved the body. A 2000 kcal week vanished on a 2000 axis. Calories without macros understate the issued week. Phase is the reason the numbers jump, and it was invisible.

### Key Decisions

- **Shared spine, not one mixed-unit chart.** kg, %, and grams keep their own registers on one week axis. (session-settled: user-approved — chosen over a single super-axis: units would flatten each other) Governs R1
- **Layout A.** Spine is primary; journey sits beside it. (session-settled: user-directed — chosen over journey-first and spine-only) Governs R2
- **Past is a scorecard.** Logged weeks show hit or miss against the target lane. (session-settled: user-directed — chosen over overlay-only lines: the job is whether we hit) Governs R4
- **Forecast is quiet.** After the current week, plan series fade. (session-settled: user-approved — chosen over full-strength plan everywhere: past scoring must stay louder) Governs R5
- **Macros replace the calorie-only bar.** Stacked protein / fat / carbs are the issued week. (session-settled: user-directed — chosen over kcal-only bars) Governs R6
- **Phase is a band, not a series recolor.** Governs R3
- **No food log in v1.** Macro actuals do not exist; fuel stays issued.

<!-- ce-section: work-relationships -->
### How This Work Fits Together

This plan is the Progress v1 visual. Later candidates, not this contract:

- Daily-weight ribbon. Depends on daily logs already stored. Can proceed independently after the spine exists.
- Energy-balance check (issued kcal vs scale-implied). Shares the week spine. Still to decide.
- Food-logged macro actuals. Outside current product identity until intake is recorded.

### Requirements

**Spine**

- R1. Weight, body fat, and macros share one week axis, one zoom, and one hover.
- R2. The spine is the primary visual; the journey is secondary beside it.
- R3. Cut, reverse, and bulk read as background bands across the spine.

**Hit, miss, and forecast**

- R4. Each logged week marks hit or miss on weight and on body fat against that week's plan target.
- R5. Series after the current week render as faded forecast. Target remains visible for the whole plan.
- R6. The fuel register is stacked issued protein, fat, and carbs. Hover names grams and the implied kcal.

**Journey**

- R7. A side plot maps weight against body fat, one point per week in time order.
- R8. DEXA weeks use a distinct mark on the journey.

**Chrome**

- R9. A short summary states how many recent logged weeks hit versus missed.

### Key Flows

Viewing Progress with a plan: the athlete opens Progress and sees phase bands, logged hit/miss on the spine, faded forecast after now, stacked issued macros, and the journey with any DEXA mark. Covers R1–R9.

Viewing Progress with no plan: the existing empty state stays. No charts.

### Acceptance Examples

- AE1. When week 12 weight is outside the target lane and weeks 8–11 are inside, week 12 reads miss and 8–11 read hit. Covers R4
- AE2. When today is week 12 of a 39-week plan, weeks 13–39 are faded and weeks 1–12 are full strength. Covers R5
- AE3. Hovering an issued week shows protein, fat, and carb grams plus kcal. There is no separate calorie-only chart. Covers R6
- AE4. A stored DEXA on week 9 appears as the distinct journey mark. Covers R8

### Scope Boundaries

In: Progress page charts and the summary chip.

Out of v1: daily-weight ribbon, energy-balance chart, food logging, Tracker table changes, new data collection.

### Assumptions

- Schedule rows already carry phase, targets, actuals, macros, and DEXA week index.
- Adherence and training feel are not the hit/miss signal; the body versus the plan is.

### Outstanding Questions

None remaining. Hit-lane, week chip, and empty-macro rendering are KTD3–KTD5.

## Planning Contract

### Key Technical Decisions

- KTD1. One ECharts instance with three stacked grids (weight, BF, macros) shares category weeks, dataZoom, and axis tooltip. Journey is a second EChart. Governs R1, R2
- KTD2. Phase bands are `markArea` on each spine grid from consecutive equal `phase` values. Colors stay mute (cut rose, reverse amber, bulk mint). Governs R3
- KTD3. Weight hit when `abs(actual − target) ≤ 0.4` kg. BF hit when `abs(actual − target) ≤ 0.6` pp. Use existing `weight_delta_kg` / `bf_delta` when present. Only weeks with `status` in `logged`, `excluded`, `partial` and a non-null actual score. Governs R4, AE1
- KTD4. The R9 chip counts a week as hit only when weight hits. BF miss still paints the BF point. Governs R9
- KTD5. Macro stacks use issued kcal (`protein_g×4`, `carbs_g×4`, `fat_g×9`). Week with `target_calories` null or 0 is a gap, not a zero bar. Future stacks at 28% opacity. Governs R5, R6
- KTD6. `current_week` from `bodycomp_get_plan` is the fade cut: index `week > current_week`. Target lines stay full-plan dashed; actuals stop at the last scored week. Governs R5, AE2
- KTD7. Journey is scatter+line of `[weight, bf]` for weeks that have both actuals. `state.dexa_weeks` (already dumped) get a larger hollow mark. Governs R7, R8, AE4
- KTD8. Chart option builders live in `client_code/ProgressCharts.py` with no Anvil UI imports so pytest can run them. `ProgressForm` only mounts.

### Technical Design

`bodycomp_get_plan` already returns `schedule[]` (`phase`, targets, actuals, macros, `status`, deltas), `current_week`, and `dexa_weeks`. No server change.

Spine option shape (directional): three `grid`s, three linked `xAxis` (category `W1…`), three `yAxis` (kg / % / kcal with `padded_value_axis` on kcal). Weight: dashed target + corridor `markArea` ±0.4 kg + solid actual with per-point green/red. BF: same without corridor fill. Macros: three stacked bar series. Shared `dataZoom` `xAxisIndex: [0,1,2]`.

Layout: `Layout.grid("minmax(0, 1.45fr) minmax(280px, 0.75fr)", spine_card, journey_card)` plus a text chip above. Empty plan keeps today’s empty state.

### Assumptions

- ECharts in the app already supports `grid`, `markArea`, and stacked bars via the existing `EChart` wrapper.
- `dexa_weeks` is a list of week indexes on the plan dump (`BodyCompService` ~line 287).

### Sequencing

U1 (pure scoring + series) then U2 (ECharts options) then U3 (ProgressForm mount). U2 depends on U1. U3 depends on U2.

### Sources

- `client_code/ProgressForm/__init__.py` — three separate `_chart` cards
- `craftify-library/client_code/CraftifyUtils/echarts_theme.py` — `padded_value_axis`
- `craftify-library/server_code/BodyCoach/schedule.py` — `WeekRow`, `weight_delta_kg`, `bf_delta`, `status`
- `server_code/BodyCompService/__init__.py` — `current_week`, `dexa_weeks`

## Implementation Units

### U1. Hit, fade, and journey points

Goal: Pure functions decide hit/miss, fade cut, macro stacks, and journey points.

Requirements: R4, R5, R6, R7, R8, R9

Files:
- `client_code/ProgressCharts.py` (add)
- `tests/test_progress_charts.py` (add)

Approach: `score_week(row)`, `week_chip(rows, current_week)`, `macro_stack(row)`, `journey_points(rows, dexa_weeks)`, `fade_after(values, current_week)`. No Anvil imports.

Test scenarios:
- Logged week with weight delta 0.2 → weight hit; 0.5 → miss (KTD3)
- BF delta 0.6 → hit; 0.7 → miss
- Planned week with no actual → no score
- Chip: 4 logged, 3 weight-hits → "3 hit · 1 miss" among recent logged (last 8 or all logged if fewer)
- Macro stack of 180/60/200 g → 720 / 540 / 800 kcal; null calories → None
- Journey skips weeks missing weight or BF; week in `dexa_weeks` flagged

Verification: `cd body-comp-tracker && .venv/bin/pytest tests/test_progress_charts.py -q`

Dependencies: none

### U2. Spine and journey ECharts options

Goal: Build the two option dicts from scored schedule data.

Requirements: R1, R3, R5, R6

Files:
- `client_code/ProgressCharts.py` (extend)
- `tests/test_progress_charts.py` (extend)
- `craftify-library/client_code/CraftifyUtils/echarts_theme.py` — reuse `padded_value_axis` only; do not fork theme

Approach: `spine_options(rows, current_week)` returns grids, phase `markArea`, shared tooltip formatter (grams + kcal). `journey_options(points)` returns scatter+line. Apply theme in the form, not in the builder, so tests assert structure without Anvil.

Test scenarios:
- Three grids and `dataZoom.xAxisIndex == [0,1,2]`
- Phase changes cut→reverse produce two markArea ranges
- Future bar series carry fade opacity 0.28
- Tooltip payload includes protein_g and kcal
- Journey DEXA point has a larger symbolSize

Verification: same pytest file

Dependencies: U1

### U3. Progress page mount

Goal: Progress shows the spine, journey, and chip; old three-card layout is gone.

Requirements: R2, AE2, AE3, empty-state flow

Files:
- `client_code/ProgressForm/__init__.py`

Approach: Keep empty state. With a plan, render chip from `week_chip`, ChartCard+EChart for spine (height ~420px) and journey (height ~420px) in the A grid. Remove the three `_chart` calls.

Test scenarios (browser, not pytest):
- `/progress` with a plan: one spine, one journey, no standalone Calories card
- Hover a past week: macros + kcal
- Weeks after `current_week` look faded
- No plan: existing empty state

Verification: open `http://localhost:3031/progress` signed in as `local@bodycomp.app`; confirm chip, phase bands, stacked macros, journey DEXA mark if scans exist

Dependencies: U2

## Verification Contract

- Unit: `cd "/Users/salikoule/My Drive/_Craftify Works/body-comp-tracker" && .venv/bin/pytest tests/test_progress_charts.py tests/test_bodycomp_service.py -q`
- Browser: Progress with the local plan — 2000 kcal weeks must have visible macro stacks; hit/miss dots on logged actuals; forecast after current week faded
- Do not change Tracker or Check-in as part of proving this plan

## Definition of Done

- R1–R9 and AE1–AE4 hold on Progress
- U1–U3 tests above pass
- Abandoned experimental chart options are not left in ProgressForm
- Product Contract IDs were not rewritten
