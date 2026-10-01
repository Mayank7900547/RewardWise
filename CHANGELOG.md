# Changelog

## Unreleased: Total Benefit / Part 1-2 scenario alignment
* Total Benefit model (reward + discount + points + other), Immediate Benefit and Final Score; `part1_baseline`, `milestone_reallocation_report`, `goal_aware_plan`.
* `scenario_groups.py` (one-slot-per-card demo model, Groups 1/2/3), `data/scenarios/` fixtures, `tests/test_scenarios.py`. 124 tests.
* UI shows reward / discount / points / other / total per expense and Immediate Benefit / Milestone Bonus / Final Score.

## v0.3.0: reliability and explainability (October 1 review baseline)
* Plain-language reasons for every recommendation (`recommend.explain_plan`), a milestone story (`recommend.plan_story`),
  and a comparison with two simpler strategies (`recommend.strategy_comparison`, `recommend.greedy_allocation`).
* UI: actual vs planned, direct vs milestone rewards, and current / projected / remaining milestone progress are shown separately.
  A fictional-data notice appears on every page.
* Shortfalls are measured against the most the planned expenses could ever add, and never suggest extra spending.
* New tests: end-to-end README scenario on the real data files, explanation and no-extra-spending tests, UI checks. 105 tests in total.
* `data/demo_shortfall.csv` for the unreachable-milestone demo. Dashboard: results cached per input.
* Unchanged on purpose: architecture, reward engine, allocation search, Docker files, the original 67 tests.

## v0.2.0: first-review scope
Modular package (`data`, `rewards`, `goals`, `recommend`, `tracker`), five-page Streamlit dashboard, whole-month allocation,
67 tests, Docker files, documentation.
