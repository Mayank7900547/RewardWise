"""Scenario / presentation helper for the 3-card slides (Part 1 and Part 2, Groups 1/2/3).

IMPORTANT - what this module is and is not
  * It is a DEMONSTRATION model: every card takes AT MOST ONE expense ("one-slot-per-card").
  * "Group 1/2/3" is a search visualisation: Group 1 is the best one-per-card allocation over the
    available expenses (this is the Part 1 baseline of the slides), Group 2 is the best one over what
    is left, Group 3 the best over what is left after that.
  * It is NOT the production optimizer. goals.recommend_allocation / goals.goal_aware_plan are the
    general monthly engine and may put several planned expenses on the same card.
Scoring still goes through goals.evaluate_allocation, so Total Benefit, caps and the once-only
milestone logic are shared with production. Only already-planned expenses are ever allocated.
"""
from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path

from .data import validate_cards
from .goals import (_score_partial, milestone_counts, milestone_reallocation_report, milestone_status,
                    strip_milestones)

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


def load_scenario(name_or_path) -> dict:
    """Load a fixture (e.g. 'part2_s3') -> dict with validated cards and plain expense dicts."""
    p = Path(name_or_path)
    if not p.suffix:
        p = SCENARIO_DIR / f"{name_or_path}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["cards"] = validate_cards(d["cards"])
    return d


def _best_one_slot(cards, expenses, available, card_ids, forced=None, prior_spend=None):
    """Exhaustive best one-expense-per-card allocation; milestones ignored (Part 1 = Total Benefit)."""
    plain = strip_milestones(cards)
    free_cards = [c for c in card_ids if not forced or c != forced[1]]
    pool = [i for i in available if not forced or i != forced[0]]
    k = min(len(free_cards), len(pool))
    best, runner, tried = None, None, 0
    for combo in permutations(pool, k):
        tried += 1
        alloc = [None] * len(expenses)
        for i, c in zip(combo, free_cards):
            alloc[i] = c
        if forced:
            alloc[forced[0]] = forced[1]
        total = _score_partial(plain, expenses, alloc, prior_spend)["immediate_benefit"]
        if best is None or total > best[0]:
            runner, best = (best[0] if best else None), (total, tuple(alloc))
        elif runner is None or total > runner:
            runner = total
    if best is None:  # nothing left to place
        alloc = [None] * len(expenses)
        if forced:
            alloc[forced[0]] = forced[1]
        best = (_score_partial(plain, expenses, alloc, prior_spend)["immediate_benefit"] if forced else 0.0, tuple(alloc))
    return {"allocation": best[1], "total": best[0], "ways_tried": tried, "runner_up": runner}


def build_groups(cards, expenses, n_groups=3, prior_spend=None):
    """Group 1 / 2 / 3 visualisation: best one-per-card allocation, then of the leftovers, etc."""
    ids, available, groups = [c["id"] for c in cards], list(range(len(expenses))), []
    for g in range(1, n_groups + 1):
        if not available:
            break
        res = _best_one_slot(cards, expenses, available, ids, None, prior_spend)
        used = [i for i, c in enumerate(res["allocation"]) if c is not None]
        groups.append({"group": g, "available": [expenses[i].get("id", i) for i in available], **res,
                       "pairs": [(expenses[i].get("id", i), res["allocation"][i]) for i in used]})
        available = [i for i in available if i not in used]
    return groups


def solve_part2(cards, expenses, prior_spend=None):
    """Part 1 baseline (Group 1) -> milestone candidates -> force each, re-solve the other cards over the
    remaining planned expenses -> keep the best -> accept only if Final Score > baseline score."""
    prior_spend = prior_spend or {}
    ids = [c["id"] for c in cards]
    n = len(expenses)
    base = _best_one_slot(cards, expenses, list(range(n)), ids, None, prior_spend)
    base_alloc = base["allocation"]
    candidates = []
    for card in cards:
        if not card.get("milestone"):
            continue
        for i, e in enumerate(expenses):
            if base_alloc[i] == card["id"] or not milestone_counts(card, e):
                continue
            if not milestone_status(card, prior_spend.get(card["id"], 0.0), float(e["amount"]))["unlocked_now"]:
                continue
            res = _best_one_slot(cards, expenses, list(range(n)), ids, (i, card["id"]), prior_spend)
            scored = _score_partial(cards, expenses, res["allocation"], prior_spend)
            candidates.append({"trigger": (expenses[i].get("id", i), card["id"]), "trigger_index": (i, card["id"]),
                               "allocation": res["allocation"], "immediate_benefit": scored["immediate_benefit"],
                               "milestone_bonus": scored["voucher_value"], "final_score": scored["total_value"]})
    best = max(candidates, key=lambda c: c["final_score"], default=None)
    baseline_score = _score_partial(cards, expenses, base_alloc, prior_spend)["total_value"]
    accepted = bool(best) and best["final_score"] > baseline_score + 1e-9
    final_alloc = best["allocation"] if accepted else base_alloc
    report = milestone_reallocation_report(cards, expenses, base_alloc, final_alloc,
                                           best["trigger_index"] if accepted else None, prior_spend)
    return {"groups": build_groups(cards, expenses, 3, prior_spend), "baseline_allocation": base_alloc,
            "candidates": candidates, "final_allocation": final_alloc, "accepted": accepted, "report": report}
