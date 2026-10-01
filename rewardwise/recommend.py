"""Card recommendation for a single planned expense (module D).

This answers "which card is best for THIS purchase?" in isolation. It is milestone-aware
(it shows when the purchase would cross a threshold) but it cannot see your other planned
expenses, so the month-wide trade-off is left to goals.recommend_allocation.

The second half of this module explains a finished monthly plan in plain language
(explain_plan, plan_story) and compares it with simpler strategies (strategy_comparison).
"""
from __future__ import annotations

from .formatting import inr, money
from .goals import best_immediate_allocation, evaluate_allocation, milestone_counts, milestone_status
from .rewards import credit_rewards, reward_for_expense

EPS = 1e-9


def rank_cards_for_expense(cards: list[dict], expense: dict, prior_spend: dict | None = None) -> list[dict]:
    """Rank cards for one expense by direct reward + any milestone voucher it would newly unlock.

    direct_value (cashback/points, after the card's monthly cap) and milestone_bonus are kept in
    separate fields so they are never confused. Ties go to the higher direct reward, then card order.
    """
    prior_spend = prior_spend or {}
    results = []
    for order, card in enumerate(cards):
        credited = credit_rewards(card, [expense])
        raw = credited["rows"][0]
        direct = raw["value"]
        parts = []
        if not raw["eligible"]:
            parts.append(f"No direct reward: {raw['reason']}.")
        elif card["reward_type"] == "cashback":
            parts.append(f"{raw['rate']:.1%} cashback on {expense['category']} = {inr(direct, 2)}.")
        else:
            parts.append(f"{raw['rate']:g} points per ₹100 on {expense['category']} = {raw['units']:,.0f} points "
                         f"(~{inr(direct, 2)} at ₹{card['point_value']:g}/point, an estimate).")
        if raw["capped"]:
            parts.append(f"Limited by the {inr(card['monthly_reward_cap'])} monthly reward cap.")
        bonus, progress_after, remaining = 0.0, None, None
        if card.get("milestone"):
            counted = float(expense["amount"]) if milestone_counts(card, expense) else 0.0
            st = milestone_status(card, prior_spend.get(card["id"], 0.0), counted)
            bonus, progress_after, remaining = st["voucher_value"], st["progress"], st["remaining"]
            if st["already_earned"]:
                parts.append(f"Milestone already earned this month; {inr(st['potential_voucher'])} voucher is not counted again.")
            elif st["unlocked_now"]:
                parts.append(f"Milestone bonus: crosses {inr(st['threshold'])} "
                             f"({inr(st['previous_spend'])} -> {inr(st['projected_spend'])}), unlocking a {inr(bonus)} voucher.")
            elif counted:
                parts.append(f"Milestone: moves progress to {st['progress']:.0%}; {inr(st['remaining'])} more eligible spend needed "
                             "(information only: RewardWise never suggests extra spending to reach it).")
            else:
                parts.append("This expense does not count towards the milestone.")
        results.append({"card_id": card["id"], "card": card["name"], "direct_value": direct,
                        "milestone_bonus": bonus, "total_value": round(direct + bonus, 2),
                        "milestone_progress_after": progress_after, "milestone_remaining": remaining,
                        "explanation": " ".join(parts), "_order": order})
    results.sort(key=lambda r: (-r["total_value"], -r["direct_value"], r["_order"]))
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank
        del r["_order"]
    return results


# ============================================================ explaining a monthly plan
def _label(expense: dict) -> str:
    return expense.get("description") or expense["category"]


def _short(card: dict) -> str:
    """'Card C — Milestone' -> 'Card C' (keeps sentences readable; tables use the full name)."""
    return card["name"].split(" — ")[0]


def _reward_sentence(card: dict, raw: dict) -> str:
    if card["reward_type"] == "cashback":
        return f"{raw['rate'] * 100:g}% cashback = {money(raw['value'])}"
    return (f"{raw['rate']:g} points per ₹100 = {raw['units']:,.0f} points "
            f"(about {money(raw['value'])} at ₹{card['point_value']:g} per point, an estimate)")


def explain_plan(cards: list[dict], expenses: list[dict], result: dict, prior_spend: dict | None = None) -> list[dict]:
    """Plain-language reasons for every recommendation in a plan from goals.recommend_allocation.

    One dict per expense: headline, value_line and a short list of `reasons`. The reasons answer, in
    order: (1) which card pays the most directly, (2) what role the card's milestone plays, and
    (3) how this purchase looks when judged ALONE versus in the whole-month plan. Every money figure
    is recomputed with goals.evaluate_allocation, so the explanation cannot drift from the numbers.
    """
    prior_spend = prior_spend or {}
    by_id = {c["id"]: c for c in cards}
    allocation = list(result["allocation"])
    total = result["total_value"]

    def month_total(changes: dict) -> float:
        alt = list(allocation)
        for index, card_id in changes.items():
            alt[index] = card_id
        return evaluate_allocation(cards, expenses, alt, prior_spend)["total_value"]

    explanations = []
    for i, expense in enumerate(expenses):
        chosen = by_id[allocation[i]]
        raws = {c["id"]: reward_for_expense(c, expense) for c in cards}
        best_direct = max(r["value"] for r in raws.values())
        best_card = next(c for c in cards if raws[c["id"]]["value"] >= best_direct - EPS)
        mine = raws[chosen["id"]]
        gap = best_direct - mine["value"]
        row = result["rows"][i]
        reasons, helps_unlock, tie_line = [], False, None

        # 1. direct reward
        if best_direct <= EPS:
            reasons.append("No card pays a direct reward on this expense, so only milestones can matter here.")
        elif gap <= EPS:
            reasons.append(f"Highest direct reward: {_short(chosen)} pays {_reward_sentence(chosen, mine)}.")
            tied = [_short(c) for c in cards if c["id"] != chosen["id"] and raws[c["id"]]["value"] >= best_direct - EPS]
            if tied:
                tie_line = f"{' and '.join(tied)} pays the same direct reward, so this expense can sit on either at no cost."
                reasons.append(tie_line)
        else:
            reasons.append(f"{_short(chosen)} pays {money(mine['value'])} directly, {money(gap)} less than "
                           f"{_short(best_card)} ({money(best_direct)}).")
        if row["capped"]:
            reasons.append(f"{_short(chosen)}'s monthly reward cap ({money(chosen['monthly_reward_cap'])}) limits the reward here.")

        # 2. the card's milestone
        ms = result["summary"][chosen["id"]].get("milestone")
        if ms and milestone_counts(chosen, expense):
            if ms["already_earned"]:
                reasons.append("The milestone on this card was already earned before this plan, so its voucher is not counted again.")
            elif ms["unlocked_now"]:
                needed = ms["previous_spend"] + ms["new_spend"] - float(expense["amount"]) < ms["threshold"]
                if needed:
                    helps_unlock = True
                    reasons.append(f"It helps unlock the {money(ms['potential_voucher'])} {ms['name'].lower()}: eligible spend on "
                                   f"{_short(chosen)} goes from {money(ms['previous_spend'])} to {money(ms['projected_spend'])}, "
                                   f"past the {money(ms['threshold'])} target.")
                    if gap <= EPS:
                        reasons.append("Unlocking it here costs no direct reward.")
                    else:
                        reasons.append(f"Unlocking it here gives up {money(gap)} of direct reward; the voucher is worth more.")
                    other_cards = [c for c in cards if c["id"] != chosen["id"]]
                    if other_cards:
                        fallback = max(other_cards, key=lambda c: raws[c["id"]]["value"])
                        equal = [f"{_label(o)} ({money(o['amount'])})" for j, o in enumerate(expenses)
                                 if j != i and allocation[j] != chosen["id"] and milestone_counts(chosen, o)
                                 and abs(month_total({i: fallback["id"], j: chosen["id"]}) - total) <= 1e-6]
                        if equal:
                            reasons.append(f"Equally good alternative: putting {' or '.join(equal[:2])} on {_short(chosen)} instead "
                                           "gives the same month total (ties are broken by a fixed rule).")
                else:
                    reasons.append("Counts towards the milestone, which other expenses on this card already unlock.")
            else:
                reasons.append(f"Counts towards the milestone ({money(ms['projected_spend'])} of {money(ms['threshold'])}), "
                               "which this plan does not reach.")

        # 3. this purchase judged alone versus in the whole-month plan
        ranking = rank_cards_for_expense(cards, expense, prior_spend)
        alone = ranking[0]
        mine_alone = next(r for r in ranking if r["card_id"] == chosen["id"])
        if (alone["card_id"] != chosen["id"] and alone["milestone_bonus"] > EPS
                and alone["total_value"] > mine_alone["total_value"] + EPS):
            drop = total - month_total({i: alone["card_id"]})
            alone_name = alone["card"].split(" — ")[0]
            head = (f"Judged on its own, {alone_name} would look better ({money(alone['total_value'])} vs "
                    f"{money(mine_alone['total_value'])}) because this purchase would unlock the "
                    f"{money(alone['milestone_bonus'])} voucher.")
            unlocked_elsewhere = result["summary"][alone["card_id"]]["milestone"]["unlocked_now"]
            if drop > 1e-6 and unlocked_elsewhere:
                reasons.append(f"{head} But this plan unlocks that voucher with other planned expenses, and moving this "
                               f"purchase to {alone_name} would lower the month's total by {money(drop)}.")
            elif drop > 1e-6:
                reasons.append(f"{head} But over the whole month, moving it to {alone_name} would lower the total by {money(drop)}.")
            elif abs(drop) <= 1e-6:
                reasons.append(f"Judged on its own, {alone_name} would also work here (it would unlock the voucher); "
                               "the month total would be the same, so this is a tie.")
                if tie_line in reasons:  # the same tie, already said here
                    reasons.remove(tie_line)

        value_line = f"{money(row['reward_value'])} direct reward" + (" + helps unlock the voucher" if helps_unlock else "")
        explanations.append({"expense": _label(expense), "amount": float(expense["amount"]), "card_id": chosen["id"],
                             "card": chosen["name"], "direct_value": row["reward_value"], "helps_unlock": helps_unlock,
                             "headline": f"{_label(expense)} ({money(expense['amount'])}) → {chosen['name']}",
                             "value_line": value_line, "reasons": reasons})
    return explanations


def plan_story(cards: list[dict], expenses: list[dict], result: dict, prior_spend: dict | None = None) -> list[str]:
    """The plan's milestone story in a few sentences per milestone card.

    Shortfalls are measured against the MOST your planned expenses could ever add (everything eligible
    on that card), not just against what this plan happens to allocate, and never suggest spending more.
    """
    allocation = list(result["allocation"])
    lines = []
    for card in cards:
        m = card.get("milestone")
        if not m:
            continue
        st = result["summary"][card["id"]]["milestone"]
        label = f"{_short(card)} ({money(m['voucher_value'])} {m['name'].lower()} at {money(m['eligible_spend'])} of eligible spend)"
        counting = [(i, e) for i, e in enumerate(expenses) if milestone_counts(card, e)]
        max_reach = st["previous_spend"] + sum(float(e["amount"]) for _, e in counting)
        if st["already_earned"]:
            lines.append(f"{label}: already earned before this plan ({money(st['previous_spend'])} spent), "
                         "so the voucher is NOT counted again.")
        elif st["unlocked_now"]:
            on_card = [(i, e) for i, e in counting if allocation[i] == card["id"]]
            names = ", ".join(f"{_label(e)} {money(e['amount'])}" for _, e in on_card)
            cost = sum(max(0.0, max(reward_for_expense(c, e)["value"] for c in cards) - reward_for_expense(card, e)["value"])
                       for i, e in enumerate(expenses) if allocation[i] == card["id"])
            lines.append(f"{label}: {money(st['previous_spend'])} spent so far, {money(m['eligible_spend'] - st['previous_spend'])} short.")
            lines.append(f"The plan puts {money(st['new_spend'])} of already-planned spending on {_short(card)} ({names}), "
                         f"reaching {money(st['projected_spend'])} and unlocking the {money(m['voucher_value'])} voucher.")
            lines.append("Doing this gives up no direct rewards elsewhere." if cost <= EPS else
                         f"Doing this gives up {money(cost)} of direct rewards elsewhere, less than the voucher is worth.")
        elif max_reach >= m["eligible_spend"]:
            why = ("it would give up at least as much direct reward as the voucher is worth" if result.get("exact")
                   else "the heuristic did not find a better way (it is not guaranteed to)")
            lines.append(f"{label}: reachable with your planned expenses, but this plan does not unlock it because {why}.")
        else:
            lines.append(f"{label}: NOT reachable. Even with every eligible planned expense on this card you would reach "
                         f"{money(max_reach)} of {money(m['eligible_spend'])}, a shortfall of {money(m['eligible_spend'] - max_reach)}. "
                         "RewardWise will not suggest extra spending to close it.")
    return lines


# ======================================================================== baselines
def greedy_allocation(cards: list[dict], expenses: list[dict], prior_spend: dict | None = None) -> tuple:
    """Baseline: go through the expenses in DATE order and give each one to the card that looks best
    for that purchase alone (direct reward + a voucher if THIS purchase crosses the target), keeping a
    running total of milestone spend. It is voucher-aware but never looks ahead, which is exactly
    what the whole-month plan does differently.
    """
    by_id = {c["id"]: c for c in cards}
    running = dict(prior_spend or {})
    allocation = [None] * len(expenses)
    for i in sorted(range(len(expenses)), key=lambda k: (str(expenses[k].get("date", "")), k)):
        top = rank_cards_for_expense(cards, expenses[i], running)[0]
        allocation[i] = top["card_id"]
        card = by_id[top["card_id"]]
        if card.get("milestone") and milestone_counts(card, expenses[i]):
            running[card["id"]] = running.get(card["id"], 0.0) + float(expenses[i]["amount"])
    return tuple(allocation)


def strategy_comparison(cards: list[dict], expenses: list[dict], plan: dict, prior_spend: dict | None = None) -> list[dict]:
    """Score three ways of assigning the same planned expenses, each split into direct rewards and
    milestone vouchers so nothing is double counted."""
    prior_spend = prior_spend or {}

    def row(name, how, result):
        return {"strategy": name, "how": how,
                "direct": result["immediate_benefit"],
                "milestone": round(sum(s["voucher_value"] for s in result["summary"].values()), 2),
                "total": result["total_value"]}

    naive = evaluate_allocation(cards, expenses, best_immediate_allocation(cards, expenses), prior_spend)
    greedy = evaluate_allocation(cards, expenses, greedy_allocation(cards, expenses, prior_spend), prior_spend)
    return [
        row("A. Best direct reward per purchase",
            "Highest cashback/points card for every expense separately. Ignores milestone vouchers.", naive),
        row("B. One purchase at a time, voucher-aware",
            "Expenses in date order; each goes to the card that looks best for that purchase alone, "
            "counting a voucher if that purchase crosses the target.", greedy),
        row("C. RewardWise whole-month plan",
            "Scores every complete assignment of the planned expenses (direct rewards + vouchers) and keeps the best.", plan),
    ]
