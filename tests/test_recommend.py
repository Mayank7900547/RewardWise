from rewardwise.formatting import inr
from rewardwise.recommend import rank_cards_for_expense
from conftest import exp


def test_ranking_orders_by_total_and_numbers_ranks(cards):
    ranked = rank_cards_for_expense(cards, exp("shopping", 7000), {"milestone": 15000})
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    assert ranked[0]["card_id"] == "milestone" and ranked[0]["total_value"] == 1035
    assert ranked[0]["direct_value"] == 35 and ranked[0]["milestone_bonus"] == 1000  # kept separate


def test_cashback_wins_when_milestone_cannot_be_crossed(cards):
    ranked = rank_cards_for_expense(cards, exp("shopping", 2000), {"milestone": 5000})
    assert ranked[0]["card_id"] == "shopping" and ranked[0]["milestone_bonus"] == 0
    assert "more eligible spend needed" in ranked[-1]["explanation"] or "more eligible spend needed" in ranked[1]["explanation"]


def test_already_earned_voucher_not_counted(cards):
    ranked = rank_cards_for_expense(cards, exp("shopping", 7000), {"milestone": 21000})
    by = {r["card_id"]: r for r in ranked}
    assert by["milestone"]["milestone_bonus"] == 0 and "already earned" in by["milestone"]["explanation"]
    assert ranked[0]["card_id"] == "shopping"


def test_ineligible_card_is_explained(all_cards):
    ranked = rank_cards_for_expense(all_cards, exp("groceries", 2000))
    d = next(r for r in ranked if r["card_id"] == "travel")
    assert d["total_value"] == 0 and "No direct reward" in d["explanation"]


def test_cap_is_mentioned(cards):
    ranked = rank_cards_for_expense(cards, exp("shopping", 20000))
    a = next(r for r in ranked if r["card_id"] == "shopping")
    assert a["direct_value"] == 500 and "monthly reward cap" in a["explanation"]


def test_inr_uses_indian_grouping():
    assert inr(1000) == "₹1,000" and inr(100000) == "₹1,00,000" and inr(1234567) == "₹12,34,567"
    assert inr(350.5, 2) == "₹350.50" and inr(-2500) == "-₹2,500"
