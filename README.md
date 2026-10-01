# RewardWise

**Goal-Oriented Credit Card Rewards and Expense Optimization**: an Open Source Tools for Data Science (OST) project.

RewardWise is a rule-based decision-support app. Given your cards and your month's expenses, it
(1) ranks cards for a single purchase and (2) recommends how to spread the **already-planned** month
across cards so the combined reward value, including milestone vouchers, is as high as possible.

> **All cards and rules are fictional** sample data for learning. No bank accounts, no live offers, no ML.

## Why month-wide planning matters
Sample scenario (fictional cards, already loaded in `data/`): ₹15,000 already spent on Card C, and ₹30,000 still
planned (groceries 8,000, shopping 7,000, dining 5,000, fuel 4,000, other 6,000). Card C pays a ₹1,000 voucher at ₹20,000.

* Judged **on its own**, the ₹7,000 shopping purchase looks best on Card C: ₹35 cashback + the ₹1,000 voucher = ₹1,035, against Card A's ₹350.
* But another planned expense (₹6,000 "other", or ₹5,000 dining) can unlock the voucher **at no cost**, because Card C pays the
  same base rate as Card A there. So the whole-month plan keeps shopping on Card A, and the month ends ₹315 better than
  putting the shopping on Card C.

| Strategy, same planned expenses | Immediate Benefit | Milestone vouchers | Final Score |
|---|---|---|---|
| A. Best direct reward per purchase (ignores vouchers) | ₹515 | ₹0 | ₹515 |
| B. One purchase at a time, voucher-aware (date order) | ₹475 | ₹1,000 | ₹1,475 |
| C. RewardWise whole-month plan | ₹515 | ₹1,000 | ₹1,515 |

Read this honestly: the plan is ₹1,000 above A (which never sees the voucher) but only ₹40 above B, because B
grabs the voucher with the groceries and gives up Card B's better points there. Every number above is asserted in
`tests/test_readme_scenario.py`. Three allocations tie at ₹1,515 (dining or "other" can unlock the voucher); the app says so.

## Status
| Area | Status |
|---|---|
| Card rules dataset (4 fictional cards; caps, exclusions, min transaction, milestones, balances) | done |
| Expense tracker (enter / import / edit, totals, by category, by card, by month) | done |
| Reward calculation (eligibility, caps, points vs cashback, milestone separated) | done |
| Card comparison with explanations and milestone awareness | done |
| Plain-language reasons for every recommendation; current / projected / remaining milestone progress; strategy comparison | done |
| Monthly allocation (exhaustive search, labeled heuristic fallback) | done (single milestone goal) |
| Streamlit dashboard (overview, portfolio, expenses, comparison, allocation) | done |
| Pytest suite | done |
| Docker / Compose | files included; **not yet run on Windows**, see [Docker checklist](docs/DOCKER_CHECKLIST.md) |
| Goal selection (points target, cashback target), HTML report, more edge cases | second review |

## Quick start
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests
```bash
python -m pytest -q
```

## Docker
```bash
docker compose up --build                      # app on http://localhost:8501
docker compose --profile test run --rm tests   # run the tests in the container
```

## Project layout
```
app.py                 Streamlit dashboard (input/display only)
rewardwise/
  data.py              load + validate cards and expenses
  rewards.py           per-expense rewards, eligibility, caps
  goals.py             milestones, monthly allocation, explanations
  recommend.py         rank cards for one purchase; explain a whole-month plan; comparison baselines
  tracker.py           monthly summaries (pandas)
  formatting.py        ₹ formatting
data/                  cards.json, expenses.csv (sample), demo_shortfall.csv (demo of an unreachable milestone)
tests/                 pytest suite
docs/                  architecture, data dictionary, design decisions, demo script, git workflow
```

## Documentation
[Architecture](docs/architecture.md) | [Data dictionary](docs/data_dictionary.md) |
[Design decisions](docs/design_decisions.md) | [Demo script](docs/DEMO_SCRIPT.md) | [Git workflow](docs/GIT_WORKFLOW.md) |
[Docker checklist](docs/DOCKER_CHECKLIST.md) | [Changelog](CHANGELOG.md)

## Assumptions and limitations
* Fictional rules; point values are assumptions, not guaranteed redemption rates.
* Only planned expenses are allocated; the tool never suggests extra spending to earn a reward.
* Allocation is exact only for small inputs (`cards ** expenses <= 100,000`), otherwise a labeled heuristic.
* Card fees, interest, issuer exclusions beyond the listed fields, and reward expiry are not modelled.
* Planned-row card assignments are ignored by the optimizer; caps ignore rewards earned earlier in the month.
* Reward totals cover planned expenses only; rewards already earned on actual spending are not included.
* Baseline B (voucher-aware, one purchase at a time) depends on date order; the whole-month plan does not.

## License
MIT, see [LICENSE](LICENSE).

## Benefit model (v0.3 scenario alignment)

RewardWise does not simply select the highest reward-rate card.

```
Total Benefit   = Reward + Discount + Points Value + Other Benefits      (per expense-card pairing)
Immediate Benefit = sum of Total Benefit over all allocated pairings       (only Reward is capped monthly)
Final Score     = Immediate Benefit + newly unlocked milestone value
```

* **Part 1 (baseline):** best complete conflict-free allocation by Total Benefit only (`goals.part1_baseline`, milestones ignored).
* **Part 2 (milestone-aware):** find milestone-triggering pairings, force one, re-solve the complete allocation (displaced
  expenses are re-evaluated), add the milestone value once, and compare with the baseline. The goal-aware allocation is
  accepted only when `Final Score > Baseline Score`. Only already-planned expenses are reassigned; no extra spending is suggested.
  `goals.milestone_reallocation_report` explains the result (trigger, displaced expense, baseline vs new allocation,
  immediate benefit lost, milestone bonus, final score, net gain).
* `goals.best_immediate_allocation` is the simple "best direct reward per purchase" **comparison** strategy. It is not Group 1.

### Production optimizer vs scenario diagrams
* The production optimizer may assign **multiple planned expenses to the same card**. Exhaustive search is used for small
  spaces (cards ** expenses <= 100,000); a heuristic fallback (best-immediate start + single-move local search) is used for larger
  ones and is **not guaranteed optimal**.
* The 3-card slides use a simplified **one-slot-per-card demonstration model** (`rewardwise/scenario_groups.py`).
  **Group 1/2/3 is a scenario/search visualization, not a separate production optimizer.**
* Fixtures for the finalized scenarios are in `data/scenarios/` and are exercised by `tests/test_scenarios.py`.
