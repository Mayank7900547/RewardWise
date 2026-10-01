"""Milestones and monthly allocation (the goal-oriented part of RewardWise).

Method (documented honestly, see docs/design_decisions.md):
  * Small problems (cards ** expenses <= EXHAUSTIVE_LIMIT): EXHAUSTIVE SEARCH over every
    assignment of expenses to cards. The best allocation under this model is guaranteed.
  * Larger problems: HEURISTIC = best-immediate-reward start + single-move local search.
    Fast and usually good, but NOT guaranteed optimal; the result says so.
Objective (Final Score) = Immediate Benefit + milestone vouchers newly unlocked this month, where
Immediate Benefit = sum of Total Benefit (Reward + Discount + Points Value + Other Benefits; only the
Reward part is capped) over every allocated expense-card pairing.
Part 1 baseline = best complete allocation by Total Benefit with milestones ignored (part1_baseline).
Part 2 = milestone-aware re-solve of the complete allocation, accepted only if Final Score > baseline.
Expenses are indivisible and only already-planned expenses are allocated; the engine never
suggests extra spending.
"""
from __future__ import annotations

from itertools import product

from .formatting import inr
from .rewards import credit_rewards, reward_for_expense

EXHAUSTIVE_LIMIT = 100_000


# ------------------------------------------------------------------------ milestones
def milestone_counts(card: dict, expense: dict) -> bool:
    """Does this expense count towards the card's spend milestone?"""
    m = card.get("milestone")
    if not m:
        return False
    if expense["category"] in card.get("excluded_categories", []):
        return False
    allowed = m.get("eligible_categories")
    return allowed is None or expense["category"] in allowed


def milestone_status(card: dict, previous_spend: float, new_spend: float) -> dict:
    """Progress towards a card's milestone, given spend already made and spend being added.

    voucher_value is non-zero ONLY when this month's new spend is what crosses the threshold.
    If the threshold was already reached before (already_earned), no voucher is counted again.
    """
    m = card["milestone"]
    threshold = float(m["eligible_spend"])
    previous, projected = float(previous_spend), float(previous_spend) + float(new_spend)
    already = previous >= threshold
    unlocked_now = previous < threshold <= projected
    return {"name": m.get("name", "Milestone voucher"), "threshold": threshold,
            "previous_spend": previous, "new_spend": float(new_spend), "projected_spend": projected,
            "current_progress": min(1.0, previous / threshold),
            "progress": min(1.0, projected / threshold), "remaining": max(0.0, threshold - projected),
            "already_earned": already, "unlocked_now": unlocked_now,
            "potential_voucher": float(m["voucher_value"]),
            "voucher_value": float(m["voucher_value"]) if unlocked_now else 0.0}


def describe_milestone(card: dict, status: dict) -> str:
    """Plain-language milestone state, including an honest shortfall message."""
    name = f"{card['name']}: {status['name']} ({inr(status['potential_voucher'])} at {inr(status['threshold'])} spend)"
    if status["already_earned"]:
        return f"{name} was already earned before this plan; it is not counted again."
    if status["unlocked_now"]:
        return f"{name} is unlocked by this plan ({inr(status['previous_spend'])} -> {inr(status['projected_spend'])})."
    return (f"{name} is NOT reached by planned expenses: {inr(status['projected_spend'])} of "
            f"{inr(status['threshold'])} ({status['progress']:.0%}), shortfall {inr(status['remaining'])}. "
            "RewardWise will not suggest extra spending just to earn it.")


# ---------------------------------------------------------------------- evaluation
COMPONENTS = ("reward_value", "discount_value", "points_value", "other_benefit_value", "unitemised_value")


def evaluate_allocation(cards, expenses, allocation, prior_spend=None):
    """Score a complete month: Immediate Benefit (Total Benefit of every pairing, reward capped)
    + milestone vouchers newly unlocked.

    prior_spend maps card id -> eligible spend already made this month (NOT a new expense).
    Result: rows (per expense, all benefit components), summary (per card), and month totals
    reward_value, discount_value, points_value, other_benefit_value, immediate_benefit,
    voucher_value, total_value (= immediate_benefit + voucher_value).
    """
    prior_spend = prior_spend or {}
    by_id = {c["id"]: c for c in cards}
    if len(allocation) != len(expenses):
        raise ValueError("allocation must have one card id per expense")
    assigned = {c["id"]: [] for c in cards}
    for index, (expense, cid) in enumerate(zip(expenses, allocation)):
        if cid not in by_id:
            raise ValueError(f"Unknown card id: {cid}")
        assigned[cid].append((index, expense))
    rows, summary = [None] * len(expenses), {}
    for card in cards:
        items = assigned[card["id"]]
        credited = credit_rewards(card, [e for _, e in items])
        for (index, expense), r in zip(items, credited["rows"]):
            rows[index] = {"description": expense.get("description", ""), "category": expense["category"],
                           "amount": expense["amount"], "card_id": card["id"], "card": card["name"],
                           "reward_value": r["value"], "reward_units": r["units"], "reward_type": r["type"],
                           "discount_value": r["discount_value"], "points_units": r["points_units"],
                           "points_value": r["points_value"], "other_benefit_value": r["other_benefit_value"],
                           "unitemised_value": r["unitemised_value"], "total_benefit": r["total_benefit"],
                           "eligible": r["eligible"], "capped": r["capped"], "note": r["reason"]}
        entry = {"reward_value": credited["value"], "reward_units": credited["units"],
                 "discount_value": credited["discount_value"], "points_value": credited["points_value"],
                 "other_benefit_value": credited["other_benefit_value"],
                 "unitemised_value": credited["unitemised_value"], "immediate_benefit": credited["total_benefit"],
                 "allocated_spend": sum(float(e["amount"]) for _, e in items), "voucher_value": 0.0}
        if card.get("milestone"):
            counted = sum(float(e["amount"]) for _, e in items if milestone_counts(card, e))
            status = milestone_status(card, prior_spend.get(card["id"], 0.0), counted)
            entry.update(milestone=status, voucher_value=status["voucher_value"],
                         milestone_progress=status["progress"], remaining_spend=status["remaining"])
        summary[card["id"]] = entry
    totals = {k: round(sum(s[k] for s in summary.values()), 2) for k in COMPONENTS}
    immediate = round(sum(s["immediate_benefit"] for s in summary.values()), 2)
    voucher = round(sum(s["voucher_value"] for s in summary.values()), 2)
    return {"rows": rows, "summary": summary, **totals, "immediate_benefit": immediate,
            "voucher_value": voucher, "total_value": round(immediate + voucher, 2)}


# ---------------------------------------------------------------------- allocation
def best_immediate_allocation(cards, expenses):
    """COMPARISON baseline ("best direct reward per purchase"): each expense on the card with the
    highest direct reward, ignoring caps, discounts, points, other benefits and milestones. It is the
    naive strategy RewardWise is compared against. It is NOT the Part 1 / Group 1 baseline: that is
    the best complete allocation by Total Benefit, see part1_baseline()."""
    return tuple(max(cards, key=lambda c: reward_for_expense(c, e)["value"])["id"] for e in expenses)


def _local_search(cards, expenses, start, prior_spend, max_passes=20):
    best = tuple(start)
    best_val = evaluate_allocation(cards, expenses, best, prior_spend)["total_value"]
    for _ in range(max_passes):
        improved = False
        for i in range(len(expenses)):
            for card in cards:
                if card["id"] == best[i]:
                    continue
                trial = best[:i] + (card["id"],) + best[i + 1:]
                val = evaluate_allocation(cards, expenses, trial, prior_spend)["total_value"]
                if val > best_val + 1e-9:
                    best, best_val, improved = trial, val, True
        if not improved:
            break
    return best


def recommend_allocation(cards, expenses, prior_spend=None, exhaustive_limit=EXHAUSTIVE_LIMIT):
    """Recommend a card for every planned expense. Result includes a 'method' description.

    Ties are broken by card order in cards.json (the first best allocation found is kept).
    """
    if not cards:
        raise ValueError("At least one card is required")
    if not expenses:
        raise ValueError("At least one planned expense is required")
    ids = [c["id"] for c in cards]
    if len(cards) ** len(expenses) <= exhaustive_limit:
        best = None
        for allocation in product(ids, repeat=len(expenses)):
            result = evaluate_allocation(cards, expenses, allocation, prior_spend)
            if best is None or result["total_value"] > best["total_value"]:
                best = {"allocation": allocation, **result}
        best["method"] = (f"Exhaustive search over all {len(cards) ** len(expenses):,} allocations: "
                          "best possible under this rule model.")
        best["exact"] = True
        return best
    allocation = _local_search(cards, expenses, best_immediate_allocation(cards, expenses), prior_spend)
    result = evaluate_allocation(cards, expenses, allocation, prior_spend)
    return {"allocation": allocation, **result, "exact": False,
            "method": "Heuristic (best-immediate start + single-move local search): good but NOT guaranteed optimal."}


def explain_allocation(cards, expenses, result, prior_spend=None):
    """One sentence per expense: why this card, and what the month-wide trade-off was."""
    by_id = {c["id"]: c for c in cards}
    allocation = list(result["allocation"])
    notes = []
    for i, expense in enumerate(expenses):
        chosen = by_id[allocation[i]]
        best_card = max(cards, key=lambda c: reward_for_expense(c, expense)["total_benefit"])
        chosen_direct = reward_for_expense(chosen, expense)["total_benefit"]
        best_direct = reward_for_expense(best_card, expense)["total_benefit"]
        if chosen["id"] == best_card["id"] or chosen_direct >= best_direct - 1e-9:
            note = ("Highest total benefit for this expense." if best_direct > 0
                    else "No card gives any benefit on this expense.")
            status = result["summary"][chosen["id"]].get("milestone")
            if status and status["unlocked_now"] and milestone_counts(chosen, expense):
                note += f" Also counts towards unlocking the {inr(status['potential_voucher'])} {status['name'].lower()}."
            notes.append(note)
            continue
        alt = list(allocation)
        alt[i] = best_card["id"]
        alt_total = evaluate_allocation(cards, expenses, alt, prior_spend)["total_value"]
        gain = round(result["total_value"] - alt_total, 2)
        if gain <= 0:
            notes.append(f"{chosen['name']} and {best_card['name']} give the same month total here; "
                         "kept the first in card order.")
            continue
        notes.append(f"{chosen['name']} gives up {inr(best_direct - chosen_direct, 2)} of total benefit vs "
                     f"{best_card['name']}, but the month's combined value is {inr(gain, 2)} higher this way "
                     "(milestone / cap effect).")
    return notes


# ------------------------------------------------------- Part 1 / Part 2 (milestone-aware)
def strip_milestones(cards):
    """Copies of the cards with milestones switched off (Part 1 ignores milestones)."""
    return [{**c, "milestone": None} for c in cards]


def part1_baseline(cards, expenses, prior_spend=None, exhaustive_limit=EXHAUSTIVE_LIMIT):
    """Part 1: best complete conflict-free allocation by Total Benefit only (milestones ignored).

    Uses the production optimizer, so several expenses may share a card. The returned dict also has
    "score": the baseline's true Final Score (including any milestone it happens to unlock anyway),
    so Part 2 compares like with like and never counts a voucher twice.
    """
    res = recommend_allocation(strip_milestones(cards), expenses, prior_spend, exhaustive_limit)
    real = evaluate_allocation(cards, expenses, res["allocation"], prior_spend)
    return {**real, "allocation": tuple(res["allocation"]), "exact": res["exact"], "method": res["method"],
            "score": real["total_value"]}


def _score_partial(cards, expenses, allocation, prior_spend=None):
    """Evaluate an allocation in which some expenses may be unallocated (None).
    Only already-planned expenses are ever used; nothing is added."""
    idx = [i for i, c in enumerate(allocation) if c is not None]
    res = evaluate_allocation(cards, [expenses[i] for i in idx], [allocation[i] for i in idx], prior_spend)
    res["indices"] = idx
    return res


def _as_tuple(expenses, alloc):
    if isinstance(alloc, dict):
        return tuple(alloc.get(i) for i in range(len(expenses)))
    return tuple(alloc)


def milestone_reallocation_report(cards, expenses, baseline, final, trigger=None, prior_spend=None):
    """Explain a milestone-triggered reallocation from the supplied data (nothing hard-coded).

    baseline / final: allocations aligned with `expenses` (tuple/list with None for an unallocated
    expense) or {expense_index: card_id}. trigger: (expense_index, card_id); if omitted it is
    detected as the pairing in `final` that newly unlocks a milestone voucher.
    """
    base, fin = _as_tuple(expenses, baseline), _as_tuple(expenses, final)
    b, f = _score_partial(cards, expenses, base, prior_spend), _score_partial(cards, expenses, fin, prior_spend)
    by_id = {c["id"]: c for c in cards}
    if trigger is None:
        for i, cid in enumerate(fin):
            card = by_id.get(cid)
            if (cid and card and card.get("milestone") and f["summary"][cid]["voucher_value"] > 0
                    and base[i] != cid and milestone_counts(card, expenses[i])):
                trigger = (i, cid)
                break
    name = lambda i: expenses[i].get("id") or expenses[i].get("description") or f"#{i}"
    displaced = []
    if trigger:
        ti, tc = trigger
        for i, cid in enumerate(base):
            if cid == tc and i != ti:
                displaced.append({"expense": name(i), "was_on": cid, "now_on": fin[i]})
    changes = [{"expense": name(i), "from": base[i], "to": fin[i]} for i in range(len(expenses)) if base[i] != fin[i]]
    pretty = lambda a: [f"{name(i)} -> {c}" for i, c in enumerate(a) if c is not None]
    return {"trigger": None if not trigger else {"expense": name(trigger[0]), "card": trigger[1]},
            "displaced": displaced, "changes": changes,
            "baseline_allocation": pretty(base), "baseline_immediate_benefit": b["immediate_benefit"],
            "baseline_milestone": b["voucher_value"], "baseline_score": b["total_value"],
            "new_allocation": pretty(fin), "new_immediate_benefit": f["immediate_benefit"],
            "milestone_bonus": f["voucher_value"], "final_score": f["total_value"],
            "net_gain": round(f["total_value"] - b["total_value"], 2),
            "immediate_benefit_lost": round(b["immediate_benefit"] - f["immediate_benefit"], 2),
            "accepted": f["total_value"] > b["total_value"] + 1e-9,
            "baseline_result": b, "final_result": f}


def goal_aware_plan(cards, expenses, prior_spend=None):
    """Production Part 1 + Part 2: baseline by Total Benefit, then the best milestone-aware complete
    allocation. The goal-aware allocation is accepted only when Final Score > baseline score."""
    base = part1_baseline(cards, expenses, prior_spend)
    best = recommend_allocation(cards, expenses, prior_spend)
    report = milestone_reallocation_report(cards, expenses, base["allocation"], best["allocation"], None, prior_spend)
    chosen = best if report["accepted"] else {**base, "allocation": base["allocation"]}
    return {"baseline": base, "goal_aware": best, "report": report, "chosen": chosen}
