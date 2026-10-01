# Design decisions (and how to defend them)

## 1. Why rule-based, not machine learning?
Card rewards are *published rules* (rates, caps, thresholds). There is nothing to learn, and a model
would be less accurate, less explainable and unnecessary. Every number on screen can be traced to a rule.

## 2. Why separate `rewards.py` from `goals.py`?
A per-purchase reward (cashback/points) and a milestone voucher are different kinds of benefit.
A voucher depends on cumulative spend and is earned once; it must not be added to every transaction
that contributes to it. Keeping them in separate modules, and in separate fields (`direct_value` vs
`milestone_bonus`), is how the project **avoids double counting**.

## 3. How is an already-earned milestone prevented from counting again?
`milestone_status` only counts the voucher when `previous_spend < threshold <= previous_spend + new_spend`.
If the threshold was reached before this plan, `already_earned` is true and the voucher value is 0.
Spending already made enters as *prior spend* (actual expenses on that card), never as a new expense.

## 4. Why evaluate the whole month instead of each transaction?
Choosing the best card per purchase can miss a milestone, and chasing a milestone with the wrong
purchase can throw away a big cashback. `evaluate_allocation` scores a *complete* assignment of all
planned expenses, so the trade-off is computed rather than guessed. The dashboard shows the
difference against the "best card per purchase" baseline.
Sample result (see README table): ₹515 for the best direct reward per purchase, ₹1,475 for a voucher-aware
purchase-by-purchase baseline, ₹1,515 for the whole-month plan.

## 4b. Which baseline are we beating? (be ready for this question)
The ₹515 baseline (A) ignores vouchers, so beating it by ₹1,000 mostly proves that vouchers exist. The fairer
baseline is B: go through the expenses in date order and give each to the card that looks best for that purchase
alone, counting a voucher when that purchase crosses the target. B scores ₹1,475 on the sample data, so the plan's
real advantage there is ₹40, because B takes the voucher with the ₹8,000 groceries and loses Card B's 5 points per ₹100.
The ₹315 figure in the explanations is a third comparison: what the month loses if the ₹7,000 shopping alone is moved
to Card C, which is what the single-purchase Card comparison page would suggest. We show all three and say which is which.

## 4c. Why "Card C for dining or other"? (ties)
Three allocations tie at ₹1,515: dining on Card C, "other" on Card C, or both (the voucher is counted once). Card C pays
the same 0.5% as Card A on both, so nothing is lost either way. The search keeps the first best allocation it finds, so
the choice follows card order in `cards.json`. This is documented, tested (`test_optimum_is_a_three_way_tie...`) and
mentioned in the explanation ("Equally good alternative").

## 5. Which algorithm, and is it optimal?
* **Exhaustive search** when `cards ** expenses <= 100,000` (for example 4 cards x 8 expenses, or
  5 cards x 7). It evaluates every assignment, so the result is the best one *under this rule model*.
* **Heuristic fallback** otherwise: start from best-immediate cards, then repeatedly move one expense to
  another card while the month total improves. Fast, usually good, **not guaranteed optimal**, and the
  result says so (`exact: False`, plus a warning in the UI).

Why not a smarter exact method (DP, integer programming)? With tiny inputs, brute force is simplest to
explain and test, and "optimal" is obvious. The starter prototype claimed exhaustive search up to
10 expenses x 5 cards; that space has 9.7 million allocations and took minutes, so the limit is now
based on the real search-space size. Upgrading to ILP (for example `scipy.optimize.milp`) is a possible
future step, not needed for the MVP.

## 6. Why does "optimal" come with caveats?
Expenses are indivisible, each card's milestone is earned once per month, point values are
assumptions, and card fees, interest and real issuer exclusions are not modelled. The app says
"best under this rule model", never "mathematically optimal in real life".

## 7. How do we avoid encouraging extra spending?
The engine only re-assigns *already planned* expenses (a test checks that allocated spend always equals planned spend).
If a milestone cannot be reached, the app reports the shortfall and states that it will not suggest extra spending
(`describe_milestone`, `plan_story`). The shortfall is measured against the most your planned expenses could ever add to
that card, not just against what one plan happens to allocate. A test scans every generated sentence for spend-more wording.

## 8. Tie-breaking
When two allocations have the same total value, the first one found wins, so card order in
`cards.json` decides. The explanation column says when two cards give the same month total.

## 9. Validation strategy
All input is cleaned in `data.py`. Notably NaN and infinite amounts are rejected (the starter only
checked `amount <= 0`, which `NaN` slips past), and errors name the offending row.

## 10. Known limitations (honest list)
* The card column on *planned* rows is ignored by the optimizer (locking planned assignments is on the roadmap).
* Reward caps do not yet account for reward already earned earlier in the month.
* One milestone per card; goal selection (points target, cashback target) is next.
* Expenses live in the browser session; use the CSV download or edit `data/expenses.csv` to keep them.
* Reward values use fictional card rules.
* Reward totals cover planned expenses only; rewards already earned on actual spending are not included.
* The add-expense form cannot be driven by Streamlit's headless test harness, so it was checked by hand in a real browser (see docs/DEMO_SCRIPT.md).

## Total Benefit and scenario alignment (v0.3)
* Objective changed from "direct rewards + vouchers" to "Total Benefit + vouchers" so the engine matches the Part 1 / Part 2 slides.
  Old cards.json files behave identically because discount, bonus points and other benefits default to zero.
* Monthly caps apply to the Reward component only; discounts and other benefits are uncapped.
* The slide scenarios need a one-expense-per-card model (e.g. S1 final score 2290; the unrestricted engine could stack E2 on Card A
  for 2340). That model lives in `scenario_groups.py` only; the production optimizer is unrestricted.
* `best_immediate_allocation` is kept as the naive comparison strategy and is deliberately not called Group 1.
