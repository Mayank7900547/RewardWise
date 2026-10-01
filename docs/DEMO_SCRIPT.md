# First-review demo script (about 6 minutes)

Every number below was checked against the running app (tests in `tests/test_app_scenarios.py`, plus a real-browser run).
Setup: `streamlit run app.py` (or `docker compose up --build` once you have verified Docker, see `DOCKER_CHECKLIST.md`),
then open http://localhost:8501. Press **F5** at any time to reset the app to the sample data.
Say early: *"All cards and reward rules are fictional. The tool only re-assigns expenses you already planned."*
(The yellow box in the sidebar says the same on every page.)

## 1. Dashboard (45 s)
* Spending row: **₹45,000** total = **₹15,000** actual (already spent) + **₹30,000** planned (still to come).
* Rewards row: **₹515** direct rewards (cashback + points) + **₹1,000** milestone reward (voucher) = **₹1,515** with the recommended plan.
* Milestone panel for Card C: current **₹15,000** (75%), planned on this card **₹6,000**, projected **₹21,000**, remaining requirement **₹0**.
* Open "How to read these numbers" once: it defines actual, planned, direct, milestone, current, projected, remaining.

## 2. Credit card portfolio (30 s)
Four fictional cards. Point at the warning banner, the rates, Card A's ₹500 cap, Card C's excluded categories, Card D's minimum transaction.

## 3. Card comparison (60 s): the single-purchase view
* Category **shopping**, amount **₹7,000**. **Card C ranks first: ₹1,035** (₹35 direct + ₹1,000 milestone) over Card A's ₹350.
* Say: "This page sees ONE purchase. It doesn't know my other expenses."
* Change the amount to **₹2,000**: Card A wins (₹100) because Card C cannot reach the target with it.

## 4. Monthly allocation (150 s): the main idea
Walk down the numbered sections:
1. **What is already spent:** the ₹15,000 is fixed history, never re-assigned.
2. **Estimated rewards:** ₹515 direct + ₹1,000 milestone = ₹1,515. "Exhaustive search over all 1,024 allocations" is stated, so we do not claim more than we prove.
   In the strategy table: **A ₹515** (ignores vouchers), **B ₹1,475** (voucher-aware, one purchase at a time), **C ₹1,515** (whole month).
   Be upfront: "The plan beats A by ₹1,000, but B by only ₹40 on this data, because B takes the voucher with the groceries."
3. **Why this plan:** Card C is ₹5,000 short; the plan puts ₹6,000 of already-planned spending on it; that gives up no direct rewards.
4. **Why each recommendation:** point at *Online shopping (₹7,000) → Card A* and read it: "Card C would look better on its own
   (₹1,035 vs ₹350), but this plan unlocks the voucher with other planned expenses, and moving the shopping to Card C would lower the month by ₹315."
   Then *Household and other → Card C*: "helps unlock the voucher, ₹15,000 to ₹21,000, costs no direct reward",
   and the line "Equally good alternative: Restaurants" explains the tie.
5. **Milestone progress:** current ₹15,000, planned ₹6,000, projected ₹21,000, remaining ₹0, green "Unlocked by this plan".

## 5. Already-earned case (30 s)
Open "Spend already made outside the tracker", enter **6000** for Card C. The voucher drops to **₹0**, total **₹515**, and the panel says
"Already earned before this plan. The voucher is not counted again." Set it back to 0.

## 6. Honest shortfall (45 s)
Expenses page, "Import expenses from CSV", choose `data/demo_shortfall.csv`, click **Replace table with uploaded CSV**, then open Monthly allocation.
Only fuel is planned, and fuel does not count for Card C: remaining requirement **₹5,000**, "NOT reachable ... shortfall of ₹5,000. RewardWise will not suggest extra spending."
Press F5 to reset.

## 7. Expenses page (45 s), last because it changes the data
Add an expense with the form (type a description, amount 1200, then click **Add expense** once; pressing Enter also submits).
Try amount 0: the app refuses with a clear message. Show the by-category and by-card tables and the CSV download. Press F5.

## 8. Close (30 s)
`python -m pytest -q` (124 tests), `git log --oneline --graph --decorate --all`, `docs/architecture.md`.

## If asked
* *"Is it optimal?"* Best under this rule model for small inputs (exhaustive); a labeled heuristic beyond 100,000 combinations.
* *"Why not machine learning?"* The rules are published; there is nothing to learn, and every number is traceable.
* *"Why does Card C get dining or other?"* A three-way tie; see design decision 4c.
* *"Does it work in Docker?"* Say only what you verified yourself using `DOCKER_CHECKLIST.md`.
