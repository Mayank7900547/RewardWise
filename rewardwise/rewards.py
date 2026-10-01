"""Reward calculation: what does ONE card pay for ONE expense (and a card's month).

Kept deliberately separate from milestones: a milestone voucher is a one-off benefit
tied to cumulative spend, so it is handled in goals.py and never mixed into the
per-transaction numbers here. That separation is what prevents double counting.

Total Benefit (per expense-card pairing) = Reward + Discount + Points Value + Other Benefits.
  * Reward   : cashback or points earned at the card's rate. ONLY this part is limited by the monthly cap.
  * Discount : optional card discount rules (rate and/or flat amount). Never capped here.
  * Points   : optional bonus points x point value. Never capped here.
  * Other    : optional flat benefits (offers, perks). Never capped here.
All four default to zero, so cards.json files written for v0.2 behave exactly as before.

Scenario fixtures may attach explicit per-pair numbers to an expense ("pair_benefits": {card_id:
{reward, discount, points, other}}, or just {"total": n} when only the pair total is known). Those
replace the rule-based calculation for that pairing so the finalized slide scenarios can be run
through the same engine.

Units: cashback rates are fractions (0.05 = 5%); points rates are points per ₹100;
point_value is rupees per point. Every returned "value" is an estimated rupee value.
"""
from __future__ import annotations


def eligibility(card: dict, expense: dict) -> tuple[bool, str]:
    """Does this card pay any direct reward on this expense? Returns (ok, reason if not)."""
    category, amount = expense["category"], float(expense["amount"])
    if category in card.get("excluded_categories", []):
        return False, f"{category} is excluded on this card"
    allowed = card.get("eligible_categories")
    if allowed is not None and category not in allowed:
        return False, f"{category} is not an eligible category"
    minimum = float(card.get("min_transaction", 0) or 0)
    if amount < minimum:
        return False, f"below the minimum transaction of {minimum:,.0f}"
    return True, ""


def rate_for(card: dict, category: str) -> float:
    return card.get("category_rates", {}).get(category, card["base_rate"])


def _matches(categories, category) -> bool:
    return categories is None or category in categories


def benefit_components(card: dict, expense: dict) -> dict:
    """Optional discount / bonus-points / other-benefit values for one expense (all default to 0)."""
    category, amount = expense["category"], float(expense["amount"])
    discount = 0.0
    for rule in card.get("discount_rules") or []:
        if _matches(rule.get("categories"), category) and amount >= float(rule.get("min_transaction", 0) or 0):
            d = amount * float(rule.get("rate", 0) or 0) + float(rule.get("flat", 0) or 0)
            if rule.get("max_discount") is not None:
                d = min(d, float(rule["max_discount"]))
            discount += d
    units = points_value = 0.0
    bp = card.get("bonus_points")
    if bp and _matches(bp.get("categories"), category):
        units = amount / 100 * float(bp.get("per_100", 0) or 0)
        points_value = units * float(bp.get("point_value", card.get("point_value", 1)))
    other = sum(float(b.get("value", 0) or 0) for b in card.get("other_benefits") or []
                if _matches(b.get("categories"), category) and amount >= float(b.get("min_transaction", 0) or 0))
    return {"discount_value": round(discount, 2), "points_units": round(units, 2),
            "points_value": round(points_value, 2), "other_benefit_value": round(other, 2)}


def _total(r: dict) -> float:
    return round(r["value"] + r["discount_value"] + r["points_value"] + r["other_benefit_value"] + r["unitemised_value"], 2)


def reward_for_expense(card: dict, expense: dict) -> dict:
    """Benefit of ONE card on ONE expense, before any monthly cap.

    "units"/"value" are the DIRECT REWARD (cashback or points earned) exactly as in v0.2.
    New fields: discount_value, points_units, points_value, other_benefit_value, total_benefit
    (= value + discount + points + other). "unitemised_value" is only used by scenario fixtures
    that give a pairing total without its breakdown (components_known is then False).
    """
    rtype = card["reward_type"]
    if rtype not in ("cashback", "points"):
        raise ValueError(f"Unsupported reward type: {rtype}")
    amount = float(expense["amount"])
    fixed = (expense.get("pair_benefits") or {}).get(card["id"])
    if fixed is not None:
        itemised = any(k in fixed for k in ("reward", "discount", "points", "other"))
        reward = float(fixed.get("reward", 0)) if itemised else 0.0
        pv = float(card.get("point_value", 1)) or 1.0
        r = {"units": reward, "value": round(reward, 2), "type": rtype, "rate": reward / amount if amount else 0.0,
             "eligible": True, "reason": "", "discount_value": float(fixed.get("discount", 0)),
             "points_units": round(float(fixed.get("points", 0)) / pv, 2), "points_value": float(fixed.get("points", 0)),
             "other_benefit_value": float(fixed.get("other", 0)),
             "unitemised_value": 0.0 if itemised else float(fixed.get("total", 0)), "components_known": itemised}
        r["total_benefit"] = _total(r)
        return r
    extras = benefit_components(card, expense)
    ok, reason = eligibility(card, expense)
    if not ok:
        r = {"units": 0.0, "value": 0.0, "type": rtype, "rate": 0.0, "eligible": False, "reason": reason}
    else:
        rate = rate_for(card, expense["category"])
        if rtype == "cashback":
            units = amount * rate
            value = units
        else:
            units = amount / 100 * rate
            value = units * float(card.get("point_value", 1))
        r = {"units": round(units, 2), "value": round(value, 2), "type": rtype, "rate": rate,
             "eligible": True, "reason": ""}
    r.update(extras, unitemised_value=0.0, components_known=True)
    r["total_benefit"] = _total(r)
    return r


def credit_rewards(card: dict, expenses: list[dict]) -> dict:
    """Apply one card's monthly reward cap to the expenses assigned to it, in order.

    The cap limits the estimated rupee value of the DIRECT REWARD only. Discounts, bonus points
    and other benefits are not capped. The reward total credited is min(cap, sum of uncapped
    rewards) whatever the order, so the search in goals.py is not sensitive to expense order.
    """
    cap = card.get("monthly_reward_cap")
    remaining = float("inf") if cap is None else float(cap)
    rows, total_value, total_units = [], 0.0, 0.0
    sums = {k: 0.0 for k in ("discount_value", "points_value", "other_benefit_value", "unitemised_value")}
    for expense in expenses:
        raw = reward_for_expense(card, expense)
        value = min(raw["value"], remaining)
        capped = value < raw["value"] - 1e-9
        if not capped:
            units = raw["units"]
        elif card["reward_type"] == "points":
            units = value / float(card.get("point_value", 1))
        else:
            units = value
        remaining -= value
        total_value += value
        total_units += units
        row = {**raw, "value": round(value, 2), "units": round(units, 2), "capped": capped}
        row["total_benefit"] = _total(row)
        for k in sums:
            sums[k] += row.get(k, 0.0)
        rows.append(row)
    out = {"rows": rows, "value": round(total_value, 2), "units": round(total_units, 2)}
    out.update({k: round(v, 2) for k, v in sums.items()})
    out["total_benefit"] = round(sum(r["total_benefit"] for r in rows), 2)
    return out
