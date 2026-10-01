"""Finalized Part 1 / Part 2 scenarios (fixtures in data/scenarios/) run through the real engine."""
import pytest

from rewardwise.goals import evaluate_allocation, goal_aware_plan, part1_baseline, recommend_allocation
from rewardwise.rewards import reward_for_expense
from rewardwise.scenario_groups import build_groups, load_scenario, solve_part2


# ------------------------------------------------------------------ Part 1
@pytest.mark.parametrize("name,rival", [("part1_s1", 240), ("part1_s2", 360), ("part1_s3", 570)])
def test_part1_total_benefit_decides(name, rival):
    s = load_scenario(name)
    cards, exp = s["cards"], s["expenses"][0]
    totals = {c["id"]: reward_for_expense(c, exp)["total_benefit"] for c in cards if c["id"] in exp["pair_benefits"]}
    assert totals["C"] == 640 and totals[s["rival_card"]] == rival
    best = recommend_allocation(cards, [exp])
    assert best["allocation"] == ("C",) and best["total_value"] == 640


# ------------------------------------------------------------------ Part 2
EXPECTED = {"part2_s1": (2015, 2290, 275), "part2_s2": (1060, 1178, 118), "part2_s3": (1640, 1810, 170),
            "part2_s4": (1640, 1860, 220), "part2_s5": (1640, 2100, 460)}


@pytest.mark.parametrize("name", list(EXPECTED))
def test_part2_scores(name):
    s = load_scenario(name)
    r = solve_part2(s["cards"], s["expenses"])
    base, final, net = EXPECTED[name]
    rep = r["report"]
    assert (rep["baseline_score"], rep["final_score"], rep["net_gain"]) == (base, final, net)
    assert r["accepted"] and rep["accepted"]
    assert rep["final_score"] == rep["new_immediate_benefit"] + rep["milestone_bonus"]
    assert rep["immediate_benefit_lost"] == rep["baseline_immediate_benefit"] - rep["new_immediate_benefit"]


def test_part2_s3_report_details():
    s = load_scenario("part2_s3")
    rep = solve_part2(s["cards"], s["expenses"])["report"]
    assert rep["trigger"] == {"expense": "E1", "card": "C"}
    assert [d["expense"] for d in rep["displaced"]] == ["E3"]
    assert rep["baseline_immediate_benefit"] == 1640 and rep["new_immediate_benefit"] == 1210
    assert rep["milestone_bonus"] == 600 and rep["immediate_benefit_lost"] == 430
    assert sorted(rep["new_allocation"]) == ["E1 -> C", "E2 -> A", "E6 -> B"]


@pytest.mark.parametrize("name", list(EXPECTED))
def test_milestone_counted_once_and_no_extra_spend(name):
    s = load_scenario(name)
    exps = s["expenses"]
    r = solve_part2(s["cards"], exps)
    fin = r["report"]["final_result"]
    unlocked = [cid for cid, e in fin["summary"].items() if e["voucher_value"] > 0]
    assert len(unlocked) == 1
    assert fin["voucher_value"] == fin["summary"][unlocked[0]]["voucher_value"]       # once, not per expense
    used = [row for row in fin["rows"]]
    assert len(used) <= len(exps) and len({id(x) for x in used}) == len(used)         # nothing duplicated or added
    planned = {(e["description"], e["amount"]) for e in exps}
    assert all((row["description"], row["amount"]) in planned for row in used)
    assert sum(row["amount"] for row in used) <= sum(e["amount"] for e in exps)


def test_displaced_expense_is_reevaluated_s1_and_s2():
    s = load_scenario("part2_s1")
    d = solve_part2(s["cards"], s["expenses"])["report"]["displaced"]
    assert d == [{"expense": "E2", "was_on": "B", "now_on": "C"}]          # displaced, then re-placed (E2 -> C = 50)
    s = load_scenario("part2_s2")
    d = solve_part2(s["cards"], s["expenses"])["report"]["displaced"]
    assert d == [{"expense": "E3", "was_on": "C", "now_on": "A"}]


def test_complete_allocations_are_compared():
    s = load_scenario("part2_s1")
    r = solve_part2(s["cards"], s["expenses"])
    assert len(r["candidates"]) == 1 and r["candidates"][0]["final_score"] == 2290
    # a candidate that does not beat the baseline is rejected
    cards = [dict(c) for c in s["cards"]]
    cards[1] = {**cards[1], "milestone": {**cards[1]["milestone"], "voucher_value": 10}}
    r2 = solve_part2(cards, s["expenses"])
    assert not r2["accepted"] and r2["report"]["final_score"] == r2["report"]["baseline_score"] == 2015


def test_groups_visualisation_s5():
    s = load_scenario("part2_s5")
    g = build_groups(s["cards"], s["expenses"])
    assert [x["total"] for x in g] == [1640, 1160, 870]
    assert g[0]["ways_tried"] == 504 and g[1]["ways_tried"] == 120 and g[2]["ways_tried"] == 6


def test_production_goal_aware_plan_allows_multiple_per_card_and_rule():
    s = load_scenario("part2_s1")
    plan = goal_aware_plan(s["cards"], s["expenses"])
    # production engine may stack expenses on one card, so it can beat the one-slot slide model (2290)
    assert plan["goal_aware"]["total_value"] >= 2290
    assert plan["chosen"]["total_value"] >= plan["baseline"]["score"]
    assert part1_baseline(s["cards"], s["expenses"])["immediate_benefit"] >= 2015


def test_cap_applies_to_reward_only():
    card = {"id": "X", "name": "X", "reward_type": "cashback", "base_rate": 0.1, "monthly_reward_cap": 100,
            "discount_rules": [{"rate": 0.05}], "bonus_points": {"per_100": 1, "point_value": 1},
            "other_benefits": [{"name": "perk", "value": 30}]}
    from rewardwise.data import validate_cards
    c = validate_cards([card])
    res = evaluate_allocation(c, [{"category": "other", "amount": 2000}], ["X"])
    assert res["reward_value"] == 100 and res["discount_value"] == 100 and res["points_value"] == 20
    assert res["other_benefit_value"] == 30 and res["immediate_benefit"] == 250 and res["total_value"] == 250
