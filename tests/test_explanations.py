"""The plain-language layer: explain_plan, plan_story, the baselines, and the no-extra-spending guarantee."""
import random

import pytest

from conftest import exp
from rewardwise.formatting import money
from rewardwise.goals import evaluate_allocation, recommend_allocation
from rewardwise.recommend import explain_plan, greedy_allocation, plan_story, strategy_comparison

PRIOR = {"milestone": 15000}
BANNED = ["you should spend", "spend an additional", "spend more", "consider spending", "top up", "spend another",
          "spend extra to reach", "worth spending"]


def month(cards, prior=PRIOR):
    planned = [exp("groceries", 8000, description="Groceries", date="2026-09-27"),
               exp("shopping", 7000, description="Online shopping", date="2026-09-28"),
               exp("dining", 5000, description="Dining", date="2026-09-28"),
               exp("other", 6000, description="Household", date="2026-09-30")]
    plan = recommend_allocation(cards, planned, prior)
    return planned, plan


def by_expense(explanations):
    return {x["expense"]: x for x in explanations}


def text(x):
    return " ".join(x["reasons"])


def test_shopping_row_explains_the_tradeoff_in_numbers(cards):
    planned, plan = month(cards)
    x = by_expense(explain_plan(cards, planned, plan, PRIOR))["Online shopping"]
    assert x["card_id"] == "shopping" and x["direct_value"] == 350
    assert "5% cashback = ₹350" in text(x)
    assert "Judged on its own, Card C would look better (₹1,035 vs ₹350)" in text(x)
    assert "lower the month's total by ₹315" in text(x)


def test_unlocking_expense_is_labelled_and_costs_nothing(cards):
    planned, plan = month(cards)
    x = by_expense(explain_plan(cards, planned, plan, PRIOR))["Household"]
    assert x["card_id"] == "milestone" and x["helps_unlock"]
    assert x["direct_value"] == 30                                  # the voucher is NOT folded into the direct reward
    assert "goes from ₹15,000 to ₹21,000" in text(x) and "costs no direct reward" in text(x)
    assert "Equally good alternative" in text(x) and "Dining" in text(x)


def test_ties_are_reported_as_ties(cards):
    planned, plan = month(cards)
    x = by_expense(explain_plan(cards, planned, plan, PRIOR))["Dining"]
    assert "this is a tie" in text(x) and not x["helps_unlock"]


def test_a_real_sacrifice_is_quantified(cards):
    planned = [exp("shopping", 7000, description="Online shopping")]
    plan = recommend_allocation(cards, planned, PRIOR)
    x = explain_plan(cards, planned, plan, PRIOR)[0]
    assert x["card_id"] == "milestone" and x["helps_unlock"]
    assert "gives up ₹315 of direct reward" in text(x)


def test_every_recommendation_has_a_headline_and_at_least_one_reason(cards):
    planned, plan = month(cards)
    for x in explain_plan(cards, planned, plan, PRIOR):
        assert x["headline"] and x["value_line"] and x["reasons"]


def test_story_when_voucher_is_unlocked(cards):
    planned, plan = month(cards)
    story = " ".join(plan_story(cards, planned, plan, PRIOR))
    assert "₹15,000 spent so far, ₹5,000 short" in story
    assert "reaching ₹21,000 and unlocking the ₹1,000 voucher" in story
    assert "gives up no direct rewards elsewhere" in story


def test_story_when_voucher_was_already_earned(cards):
    planned, plan = month(cards, {"milestone": 21000})
    story = " ".join(plan_story(cards, planned, plan, {"milestone": 21000}))
    assert "already earned" in story and "NOT counted again" in story


def test_story_reports_an_honest_shortfall_without_encouraging_spending(cards):
    planned = [exp("fuel", 4000, description="Fuel")]              # fuel is excluded from Card C's milestone
    plan = recommend_allocation(cards, planned, PRIOR)
    story = " ".join(plan_story(cards, planned, plan, PRIOR))
    assert "NOT reachable" in story and "shortfall of ₹5,000" in story
    assert "will not suggest extra spending" in story


def test_shortfall_uses_the_most_the_plan_could_reach_not_just_what_it_allocated(cards):
    planned = [exp("other", 2000, description="Other")]            # 15,000 + 2,000 = 17,000 at best
    plan = recommend_allocation(cards, planned, PRIOR)
    story = " ".join(plan_story(cards, planned, plan, PRIOR))
    assert "you would reach ₹17,000 of ₹20,000, a shortfall of ₹3,000" in story


def test_reachable_but_not_worth_it_is_said_plainly(cards):
    stingy = [dict(c, milestone=dict(c["milestone"], voucher_value=20)) if c["id"] == "milestone" else c for c in cards]
    planned = [exp("groceries", 5000, description="Groceries")]    # Card B pays Rs 50; Card C would pay 25 + 20
    plan = recommend_allocation(stingy, planned, PRIOR)
    assert plan["allocation"] == ("grocery",)
    story = " ".join(plan_story(stingy, planned, plan, PRIOR))
    assert "reachable with your planned expenses" in story and "at least as much direct reward" in story


def test_no_text_ever_tells_the_user_to_spend_more(cards, all_cards):
    scenarios = [(cards, month(cards)[0], PRIOR), (cards, [exp("fuel", 4000, description="Fuel")], PRIOR),
                 (cards, [exp("other", 2000, description="Other")], PRIOR),
                 (all_cards, [exp("groceries", 1000, description="G"), exp("shopping", 500, description="S")], {"milestone": 19990})]
    for cs, planned, prior in scenarios:
        plan = recommend_allocation(cs, planned, prior)
        combined = " ".join(plan_story(cs, planned, plan, prior) + [t for x in explain_plan(cs, planned, plan, prior) for t in x["reasons"]]).lower()
        assert not any(phrase in combined for phrase in BANNED), combined


def test_allocation_only_moves_planned_spend_it_never_adds_any(all_cards):
    rng = random.Random(7)
    categories = ["groceries", "shopping", "dining", "fuel", "travel", "utilities", "other"]
    for _ in range(25):
        planned = [exp(rng.choice(categories), rng.randrange(200, 9000, 100)) for _ in range(rng.randint(1, 6))]
        prior = {"milestone": float(rng.randrange(0, 21000, 500))}
        plan = recommend_allocation(all_cards, planned, prior)
        assert len(plan["allocation"]) == len(planned)
        assert sum(v["allocated_spend"] for v in plan["summary"].values()) == pytest.approx(sum(e["amount"] for e in planned))


def test_greedy_baseline_goes_in_date_order_not_row_order(cards):
    a_and_c = [c for c in cards if c["id"] in ("shopping", "milestone")]
    rows = [exp("other", 6000, date="2026-09-20"), exp("other", 6000, date="2026-09-10")]   # later date listed first
    assert greedy_allocation(a_and_c, rows, PRIOR) == ("shopping", "milestone")            # earlier date takes the voucher


def test_strategy_rows_add_up_and_the_plan_is_never_worse(cards):
    planned, plan = month(cards)
    rows = strategy_comparison(cards, planned, plan, PRIOR)
    assert len(rows) == 3
    for r in rows:
        assert r["direct"] + r["milestone"] == pytest.approx(r["total"])
    assert rows[2]["total"] >= max(rows[0]["total"], rows[1]["total"])


def test_money_drops_paise_only_for_whole_rupees():
    assert money(350) == "₹350" and money(0) == "₹0" and money(1515) == "₹1,515"
    assert money(350.5) == "₹350.50" and money(100000) == "₹1,00,000"
