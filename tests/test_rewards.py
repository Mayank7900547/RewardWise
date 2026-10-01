import pytest

from rewardwise.rewards import credit_rewards, eligibility, reward_for_expense
from conftest import exp


def card(**kw):
    base = {"id": "t", "name": "T", "reward_type": "cashback", "base_rate": 0.01, "category_rates": {},
            "point_value": 1}
    return {**base, **kw}


def test_shopping_cashback_is_five_percent(cards):
    assert reward_for_expense(cards[0], exp("shopping", 7000))["value"] == 350


def test_base_rate_applies_outside_bonus_category(cards):
    assert reward_for_expense(cards[0], exp("dining", 1000))["value"] == 5  # 0.5%


def test_grocery_points_and_rupee_value_are_separate(cards):
    r = reward_for_expense(cards[1], exp("groceries", 8000))
    assert r["units"] == 400 and r["value"] == 80 and r["type"] == "points"


def test_excluded_category_earns_nothing():
    c = card(excluded_categories=["fuel"])
    r = reward_for_expense(c, exp("fuel", 5000))
    assert r["value"] == 0 and not r["eligible"] and "excluded" in r["reason"]


def test_eligible_categories_whitelist():
    c = card(eligible_categories=["travel"])
    assert reward_for_expense(c, exp("travel", 1000))["value"] == 10
    assert eligibility(c, exp("dining", 1000))[0] is False


def test_minimum_transaction():
    c = card(min_transaction=500)
    assert reward_for_expense(c, exp("dining", 499))["value"] == 0
    assert reward_for_expense(c, exp("dining", 500))["value"] == 5


def test_unsupported_reward_type_raises():
    with pytest.raises(ValueError):
        reward_for_expense(card(reward_type="miles"), exp("dining", 100))


def test_monthly_cashback_cap(cards):
    out = credit_rewards(cards[0], [exp("shopping", 7000)] * 3)
    assert out["value"] == 500
    assert [r["capped"] for r in out["rows"]] == [False, True, True]


def test_cap_total_is_order_independent():
    c = card(monthly_reward_cap=100, category_rates={"shopping": 0.05})
    a = credit_rewards(c, [exp("shopping", 1000), exp("shopping", 3000)])["value"]
    b = credit_rewards(c, [exp("shopping", 3000), exp("shopping", 1000)])["value"]
    assert a == b == 100


def test_capped_points_units_follow_value():
    c = card(reward_type="points", base_rate=5, point_value=0.2, monthly_reward_cap=50)
    out = credit_rewards(c, [exp("groceries", 8000)])  # uncapped value 80, cap 50
    assert out["value"] == 50 and out["units"] == 250
