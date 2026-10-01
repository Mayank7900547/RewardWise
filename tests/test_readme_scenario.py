"""End-to-end check of the README scenario, using the REAL data files (data/cards.json, data/expenses.csv).

Scenario: Rs 15,000 already spent on Card C (actual); planned groceries 8,000, shopping 7,000,
dining 5,000, fuel 4,000, other 6,000; Card C gives a Rs 1,000 voucher at Rs 20,000.
"""
from itertools import product

import pytest

from conftest import ROOT
from rewardwise.data import load_expenses
from rewardwise.goals import best_immediate_allocation, evaluate_allocation, recommend_allocation
from rewardwise.recommend import greedy_allocation, rank_cards_for_expense, strategy_comparison
from rewardwise.tracker import available_months, filter_month, planned_expenses, prior_spend_from_actuals, summarize


@pytest.fixture(scope="module")
def sc(all_cards):
    df = load_expenses(ROOT / "data/expenses.csv", [c["id"] for c in all_cards])
    month_df = filter_month(df, available_months(df)[-1])
    planned = planned_expenses(month_df)
    prior = prior_spend_from_actuals(all_cards, month_df)
    return {"cards": all_cards, "df": month_df, "planned": planned, "prior": prior,
            "plan": recommend_allocation(all_cards, planned, prior)}


def card_for(sc, description_start):
    """Card id the plan chose for the planned expense whose description starts with the given text."""
    for expense, card_id in zip(sc["planned"], sc["plan"]["allocation"]):
        if expense["description"].startswith(description_start):
            return card_id
    raise AssertionError(f"no planned expense starting with {description_start!r}")


def test_sample_data_matches_the_readme_scenario(sc):
    s = summarize(sc["df"])
    assert s["actual"] == 15000 and s["planned"] == 30000
    by_category = {e["category"]: e["amount"] for e in sc["planned"]}
    assert by_category == {"groceries": 8000, "shopping": 7000, "dining": 5000, "fuel": 4000, "other": 6000}
    assert sc["prior"] == {"milestone": 15000}          # the 15,000 counts as history, not as a new expense
    milestone = next(c for c in sc["cards"] if c["id"] == "milestone")["milestone"]
    assert milestone["eligible_spend"] == 20000 and milestone["voucher_value"] == 1000


def test_whole_month_plan_beats_best_card_per_purchase(sc):
    naive = evaluate_allocation(sc["cards"], sc["planned"], best_immediate_allocation(sc["cards"], sc["planned"]), sc["prior"])
    assert sc["plan"]["exact"]
    assert naive["total_value"] == 515
    assert sc["plan"]["total_value"] == 1515


def test_plan_keeps_card_a_for_shopping_and_unlocks_voucher_elsewhere(sc):
    assert card_for(sc, "Online shopping") == "shopping"       # Card A keeps its Rs 350 cashback
    assert card_for(sc, "Monthly groceries") == "grocery"
    assert card_for(sc, "Fuel") == "travel"
    ms = sc["plan"]["summary"]["milestone"]["milestone"]
    assert ms["unlocked_now"] and ms["projected_spend"] >= 20000 and ms["remaining"] == 0
    assert "milestone" in {card_for(sc, "Restaurants"), card_for(sc, "Household")}   # dining OR other unlocks it


def test_direct_rewards_and_voucher_are_counted_separately(sc):
    direct = sum(v["reward_value"] for v in sc["plan"]["summary"].values())
    voucher = sum(v["voucher_value"] for v in sc["plan"]["summary"].values())
    assert (direct, voucher) == (515, 1000)
    assert direct + voucher == sc["plan"]["total_value"]


def test_voucher_is_counted_once_even_if_two_expenses_could_unlock_it(sc):
    both = ["grocery", "shopping", "milestone", "travel", "milestone"]     # dining AND other on Card C
    r = evaluate_allocation(sc["cards"], sc["planned"], both, sc["prior"])
    assert sum(v["voucher_value"] for v in r["summary"].values()) == 1000
    assert r["total_value"] == 1515


def test_actual_spend_is_history_and_planned_spend_is_never_invented(sc):
    allocated = sum(v["allocated_spend"] for v in sc["plan"]["summary"].values())
    assert allocated == 30000                                          # exactly the planned expenses
    ms = sc["plan"]["summary"]["milestone"]["milestone"]
    assert ms["previous_spend"] == 15000 and ms["new_spend"] <= 11000  # never more than planned eligible spend


def test_already_earned_voucher_is_not_counted_again(sc):
    prior = {"milestone": 21000}
    plan = recommend_allocation(sc["cards"], sc["planned"], prior)
    assert plan["total_value"] == 515
    assert plan["summary"]["milestone"]["milestone"]["already_earned"]
    assert plan["summary"]["milestone"]["voucher_value"] == 0


def test_single_purchase_view_prefers_card_c_but_the_month_prefers_card_a(sc):
    alone = rank_cards_for_expense(sc["cards"], {"category": "shopping", "amount": 7000}, sc["prior"])
    assert alone[0]["card_id"] == "milestone" and alone[0]["total_value"] == 1035
    moved = list(sc["plan"]["allocation"])
    moved[[e["description"] for e in sc["planned"]].index("Online shopping")] = "milestone"
    assert evaluate_allocation(sc["cards"], sc["planned"], moved, sc["prior"])["total_value"] == 1515 - 315


def test_strategy_comparison_numbers(sc):
    a, b, c = strategy_comparison(sc["cards"], sc["planned"], sc["plan"], sc["prior"])
    assert (a["total"], b["total"], c["total"]) == (515, 1475, 1515)
    assert (a["milestone"], b["milestone"], c["milestone"]) == (0, 1000, 1000)
    assert all(abs(r["direct"] + r["milestone"] - r["total"]) < 1e-9 for r in (a, b, c))
    assert c["total"] >= b["total"] >= a["total"]


def test_optimum_is_a_three_way_tie_that_only_moves_dining_or_other(sc):
    """Documents the tie-break the reviewers may ask about: dining or 'other' can unlock the voucher."""
    ids = [c["id"] for c in sc["cards"]]
    scored = [(evaluate_allocation(sc["cards"], sc["planned"], a, sc["prior"])["total_value"], a)
              for a in product(ids, repeat=len(sc["planned"]))]
    best = max(v for v, _ in scored)
    optima = [a for v, a in scored if abs(v - best) < 1e-9]
    assert best == 1515 and len(optima) == 3
    assert all(a[0] == "grocery" and a[1] == "shopping" and a[3] == "travel" for a in optima)
    assert sc["plan"]["allocation"] in optima


def test_demo_shortfall_csv_reports_the_shortfall_honestly(all_cards):
    """data/demo_shortfall.csv is used in the live demo: only fuel is planned, and fuel does not count for Card C."""
    from rewardwise.recommend import plan_story
    df = load_expenses(ROOT / "data/demo_shortfall.csv", [c["id"] for c in all_cards])
    planned, prior = planned_expenses(df), prior_spend_from_actuals(all_cards, df)
    plan = recommend_allocation(all_cards, planned, prior)
    story = " ".join(plan_story(all_cards, planned, plan, prior))
    assert prior == {"milestone": 15000} and plan["summary"]["milestone"]["milestone"]["remaining"] == 5000
    assert "shortfall of ₹5,000" in story and "will not suggest extra spending" in story
