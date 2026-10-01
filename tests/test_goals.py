import pytest

from rewardwise.goals import (best_immediate_allocation, describe_milestone, evaluate_allocation,
                              explain_allocation, milestone_status, recommend_allocation)
from conftest import exp


def test_milestone_unlocked_only_when_crossed(cards):
    c = cards[2]
    assert milestone_status(c, 15000, 5000)["voucher_value"] == 1000
    assert milestone_status(c, 15000, 4999)["voucher_value"] == 0


def test_already_earned_milestone_is_not_counted_again(cards):
    st = milestone_status(cards[2], 21000, 5000)
    assert st["already_earned"] and st["voucher_value"] == 0
    assert "already earned" in describe_milestone(cards[2], st)
    result = evaluate_allocation(cards, [exp("other", 5000)], ["milestone"], {"milestone": 21000})
    assert result["summary"]["milestone"]["voucher_value"] == 0


def test_milestone_spend_respects_excluded_categories(all_cards):
    c = next(x for x in all_cards if x["id"] == "milestone")  # fuel excluded
    r = evaluate_allocation([c], [exp("fuel", 9000)], ["milestone"], {"milestone": 15000})
    assert r["summary"]["milestone"]["voucher_value"] == 0
    assert r["summary"]["milestone"]["remaining_spend"] == 5000


def test_shortfall_is_reported_honestly(cards):
    r = recommend_allocation([cards[2]], [exp("other", 3000)], {"milestone": 5000})
    s = r["summary"]["milestone"]["milestone"]
    assert s["remaining"] == 12000 and not s["unlocked_now"]  # 20,000 - 5,000 - 3,000
    assert "NOT reached" in describe_milestone(cards[2], s) and "extra spending" in describe_milestone(cards[2], s)


def test_single_expense_prefers_voucher_over_cashback(cards):
    r = recommend_allocation(cards, [exp("shopping", 7000)], {"milestone": 15000})
    assert r["allocation"] == ("milestone",) and r["total_value"] == 1035


def test_does_not_sacrifice_cashback_when_another_expense_can_unlock(cards):
    """Brief's scenario: another planned expense can unlock Card C, so keep Card A's 5%."""
    planned = [exp("shopping", 7000), exp("other", 6000)]
    r = recommend_allocation(cards, planned, {"milestone": 15000})
    assert r["allocation"] == ("shopping", "milestone")
    assert r["total_value"] == 350 + 30 + 1000


def test_optimum_is_never_worse_than_best_immediate_baseline(cards):
    planned = [exp("groceries", 8000), exp("shopping", 7000), exp("dining", 5000), exp("other", 6000)]
    opt = recommend_allocation(cards, planned, {"milestone": 15000})
    base = evaluate_allocation(cards, planned, best_immediate_allocation(cards, planned), {"milestone": 15000})
    assert opt["total_value"] >= base["total_value"]


def test_exhaustive_result_is_exact_and_heuristic_is_labeled(cards):
    planned = [exp("shopping", 7000), exp("other", 6000), exp("groceries", 8000)]
    exact = recommend_allocation(cards, planned, {"milestone": 15000})
    heur = recommend_allocation(cards, planned, {"milestone": 15000}, exhaustive_limit=1)
    assert exact["exact"] and "Exhaustive" in exact["method"]
    assert not heur["exact"] and "NOT guaranteed optimal" in heur["method"]
    assert heur["total_value"] <= exact["total_value"]


def test_heuristic_handles_large_inputs(cards):
    planned = [exp("shopping", 2000)] * 14
    r = recommend_allocation(cards, planned, {"milestone": 0})
    assert len(r["allocation"]) == 14 and not r["exact"]


def test_monthly_cap_inside_evaluation(cards):
    r = evaluate_allocation(cards, [exp("shopping", 7000)] * 3, ["shopping"] * 3)
    assert r["summary"]["shopping"]["reward_value"] == 500


def test_bad_inputs_raise(cards):
    with pytest.raises(ValueError):
        evaluate_allocation(cards, [exp("other", 1)], ["nope"])
    with pytest.raises(ValueError):
        evaluate_allocation(cards, [exp("other", 1)], [])
    with pytest.raises(ValueError):
        recommend_allocation([], [exp("other", 1)])
    with pytest.raises(ValueError):
        recommend_allocation(cards, [])


def test_explanations_mention_milestone_unlock(cards):
    planned = [exp("shopping", 7000), exp("other", 6000)]
    r = recommend_allocation(cards, planned, {"milestone": 15000})
    notes = explain_allocation(cards, planned, r, {"milestone": 15000})
    assert "unlocking" in notes[1]


def test_explanation_quantifies_a_real_tradeoff(cards):
    planned = [exp("shopping", 7000)]
    r = recommend_allocation(cards, planned, {"milestone": 15000})
    note = explain_allocation(cards, planned, r, {"milestone": 15000})[0]
    assert "gives up" in note and "higher" in note
