"""RewardWise dashboard. Run with: streamlit run app.py

The UI only handles input and display; every calculation lives in the rewardwise package.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

from rewardwise.data import CATEGORIES, STATUSES, load_cards, load_expenses, normalize_expenses
from rewardwise.formatting import inr, money
from rewardwise.goals import best_immediate_allocation, evaluate_allocation, recommend_allocation
from rewardwise.recommend import explain_plan, plan_story, rank_cards_for_expense, strategy_comparison
from rewardwise.rewards import reward_for_expense
from rewardwise.scenario_groups import load_scenario, solve_part2
from rewardwise.tracker import (available_months, filter_month, planned_expenses,
                                prior_spend_from_actuals, summarize)

DATA = Path(__file__).parent / "data"
PAGES = ["Dashboard", "Credit card portfolio", "Expenses", "Card comparison", "Monthly allocation", "Scenario Walkthroughs (Part 1 & 2)"]

st.set_page_config(page_title="RewardWise", page_icon="💳", layout="wide")

FICTIONAL = ("**Fictional sample data.** Every card, issuer and reward rule in RewardWise is made up for this educational "
             "project. Point values are estimates, not real redemption rates.")
NO_EXTRA_SPEND = "RewardWise only re-assigns expenses you had already planned. It never suggests spending extra to earn a reward."


# ---------------------------------------------------------------------------- state
def init_state():
    if "cards" not in st.session_state:
        st.session_state.cards = load_cards(DATA / "cards.json")
    ids = [c["id"] for c in st.session_state.cards]
    if "base" not in st.session_state:  # table fed to the editor; changes only via add / upload / reset
        st.session_state.base = load_expenses(DATA / "expenses.csv", ids)
        st.session_state.clean = st.session_state.base.copy()  # last valid edited table
        st.session_state.version = 0


def card_names():
    return {c["id"]: c["name"] for c in st.session_state.cards}


def month_picker(key):
    months = available_months(st.session_state.clean)
    if not months:
        return None
    return st.selectbox("Month", months, index=len(months) - 1, key=key)


@st.cache_data(show_spinner="Searching allocations...")
def _search(cards, planned, prior):
    """The exhaustive search can take a second or two for ~8 expenses, so cache it per input."""
    return recommend_allocation(cards, planned, prior)


def legend():
    with st.expander("How to read these numbers"):
        st.markdown(
            "- **Actual** expenses are already spent: fixed history, never re-assigned to another card.\n"
            "- **Planned** expenses are still to come: the only ones RewardWise recommends cards for.\n"
            "- **Total Benefit** of a pairing = Reward + Discount + Points Value + Other Benefits. Reward is the cashback or points a card "
            "pays (points use an *estimated* rupee value); only Reward is subject to the monthly cap.\n"
            "- **Immediate Benefit** = the sum of Total Benefit over all allocated expenses. **Final Score** = Immediate Benefit + newly unlocked milestone value.\n"
            "- **Milestone rewards** are one-off vouchers unlocked when eligible spend on a card reaches a target. "
            "They are counted once and never mixed into the per-purchase numbers.\n"
            "- **Current progress** = actual spend so far. **Projected progress** = actual spend + the planned "
            "expenses the plan puts on that card. **Remaining requirement** = target minus projected.\n"
            "- Reward totals cover the planned expenses only; rewards already earned on actual spending are not included.")


def milestone_panel(card, prior, summary=None):
    """Current vs projected progress and what remains, for one card's milestone."""
    m = card["milestone"]
    threshold = float(m["eligible_spend"])
    current = prior.get(card["id"], 0.0)
    with st.container(border=True):
        st.markdown(f"**{card['name']}: {m['name']}** ({inr(m['voucher_value'])} once {inr(threshold)} of eligible spend is reached)")
        st.caption("Current progress: actual spend so far")
        st.progress(min(1.0, current / threshold), text=f"{inr(current)} of {inr(threshold)} ({min(1.0, current / threshold):.0%})")
        if summary is None:
            st.caption("No planned expenses this month, so there is no projection.")
            return
        ms = summary["milestone"]
        st.caption("Projected progress: actual spend + the planned expenses this plan puts on the card")
        st.progress(ms["progress"], text=f"{inr(ms['projected_spend'])} of {inr(threshold)} ({ms['progress']:.0%})")
        a, b, c, d = st.columns(4)
        a.metric("Current (actual spend)", inr(ms["previous_spend"]))
        b.metric("Planned on this card", inr(ms["new_spend"]))
        c.metric("Projected", inr(ms["projected_spend"]))
        d.metric("Remaining requirement", inr(ms["remaining"]))
        if ms["already_earned"]:
            st.info("Already earned before this plan. The voucher is not counted again.")
        elif ms["unlocked_now"]:
            st.success(f"Unlocked by this plan: milestone reward {inr(ms['potential_voucher'])} (counted once).")
        else:
            st.warning("Not reached by this plan. RewardWise will not suggest extra spending to reach it.")


def compute_plan(month, extra_prior=None):
    """Shared by the dashboard and the allocation page."""
    cards, df = st.session_state.cards, filter_month(st.session_state.clean, month)
    planned = planned_expenses(df)
    prior = prior_spend_from_actuals(cards, df)
    for cid, extra in (extra_prior or {}).items():
        prior[cid] = prior.get(cid, 0.0) + extra
    if not planned:
        return df, planned, prior, None, None
    best = _search(cards, planned, prior)
    base = evaluate_allocation(cards, planned, best_immediate_allocation(cards, planned), prior)
    return df, planned, prior, best, base


# --------------------------------------------------------------------------- pages
def page_dashboard():
    st.header("Dashboard overview")
    month = month_picker("dash_month")
    if month is None:
        st.info("No expenses yet. Add some on the Expenses page.")
        return
    cards = st.session_state.cards
    df, planned, prior, best, base = compute_plan(month)
    s = summarize(df, card_names())
    st.markdown("**Spending**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total expenses", inr(s["total"]))
    c2.metric("Actual (already spent)", inr(s["actual"]))
    c3.metric("Planned (still to come)", inr(s["planned"]))
    if best:
        st.markdown("**Estimated rewards on the planned expenses, with the recommended plan**")
        r1, r2, r3 = st.columns(3)
        r1.metric("Immediate Benefit (reward + discount + points + other)", money(best["immediate_benefit"]))
        r2.metric("Milestone Bonus (vouchers)", money(best["voucher_value"]))
        r3.metric("Final Score with recommended plan", money(best["total_value"]),
                  delta=f"{money(best['total_value'] - base['total_value'])} vs best direct reward per purchase")
    left, right = st.columns(2)
    with left:
        st.subheader("Spending by category")
        if not s["by_category"].empty:
            st.bar_chart(s["by_category"].set_index("category")[["actual", "planned"]])
    with right:
        st.subheader("Spending by card")
        if s["by_card"].empty:
            st.caption("No expenses have a card assigned yet (set the card on 'actual' expenses).")
        else:
            st.dataframe(s["by_card"].drop(columns=["card"]).rename(columns={"card_name": "card"}), hide_index=True, width="stretch")
    st.subheader("Milestone progress")
    shown = False
    for card in cards:
        if card.get("milestone"):
            shown = True
            milestone_panel(card, prior, best["summary"][card["id"]] if best else None)
    if not shown:
        st.caption("No cards with milestones.")
    legend()
    st.caption("All card rules are fictional sample data.")


def page_portfolio():
    st.header("Credit card portfolio")
    st.warning("All cards below are FICTIONAL sample cards created for this educational project.")
    cards = st.session_state.cards
    overview = pd.DataFrame([{
        "Card": c["name"], "Issuer": c["issuer"], "Type": c["reward_type"],
        "Monthly reward cap": inr(c["monthly_reward_cap"]) if c["monthly_reward_cap"] is not None else "none",
        "Milestone": (f"{inr(c['milestone']['voucher_value'])} at {inr(c['milestone']['eligible_spend'])}" if c["milestone"] else "none"),
        "Balance": f"{c['reward_balance']:,.0f} " + ("points" if c["reward_type"] == "points" else "₹ cashback"),
    } for c in cards])
    st.dataframe(overview, hide_index=True, width="stretch")
    for c in cards:
        with st.expander(c["name"]):
            unit = "cashback" if c["reward_type"] == "cashback" else "points per ₹100"
            fmt = (lambda r: f"{r:.1%}") if c["reward_type"] == "cashback" else (lambda r: f"{r:g}")
            rows = [{"Category": "all others (base)", "Rate": f"{fmt(c['base_rate'])} {unit}"}]
            rows += [{"Category": k, "Rate": f"{fmt(v)} {unit}"} for k, v in c["category_rates"].items()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            if c["reward_type"] == "points":
                st.write(f"Assumed value: ₹{c['point_value']:g} per point (an estimate, not a guaranteed redemption rate)")
            st.write(f"Eligible categories: {', '.join(c['eligible_categories']) if c['eligible_categories'] else 'all'}")
            st.write(f"Excluded categories: {', '.join(c['excluded_categories']) or 'none'}")
            st.write(f"Minimum transaction: {inr(c['min_transaction'])}")


def page_expenses():
    st.header("Expense entry and tracking")
    cards = st.session_state.cards
    ids = [c["id"] for c in cards]
    with st.expander("Add an expense", expanded=False):
        with st.form("add_expense", clear_on_submit=True):
            a, b, c_ = st.columns(3)
            date = a.date_input("Date")
            desc = b.text_input("Description / merchant")
            category = c_.selectbox("Category", CATEGORIES)
            d, e, f = st.columns(3)
            amount = d.number_input("Amount (₹)", min_value=0.0, step=100.0)
            status = e.selectbox("Status", STATUSES)
            card = f.selectbox("Card used (optional)", [""] + ids, format_func=lambda i: card_names().get(i, "— none —"))
            if st.form_submit_button("Add expense"):
                row = pd.DataFrame([{"date": str(date), "description": desc, "category": category,
                                     "amount": amount, "status": status, "card": card}])
                try:
                    new = normalize_expenses(pd.concat([st.session_state.clean, row], ignore_index=True), ids)
                except ValueError as err:
                    st.error(f"Could not add: {err}")
                else:
                    st.session_state.base = st.session_state.clean = new
                    st.session_state.version += 1
                    st.rerun()
    up = st.file_uploader("Import expenses from CSV (columns: date, description, category, amount, status, card)", type="csv")
    if up is not None and st.button("Replace table with uploaded CSV"):
        try:
            new = normalize_expenses(pd.read_csv(up), ids)
        except (ValueError, pd.errors.ParserError) as err:
            st.error(f"Could not import: {err}")
        else:
            st.session_state.base = st.session_state.clean = new
            st.session_state.version += 1
            st.rerun()
    st.caption("Edit cells directly; use the + row at the bottom to add. 'actual' = already spent, 'planned' = still to come. "
               "The optimizer currently ignores the card column on planned rows.")
    edited = st.data_editor(
        st.session_state.base, num_rows="dynamic", width="stretch", key=f"editor_{st.session_state.version}",
        column_config={
            "category": st.column_config.SelectboxColumn(options=list(CATEGORIES), required=True),
            "status": st.column_config.SelectboxColumn(options=list(STATUSES), required=True),
            "card": st.column_config.SelectboxColumn(options=ids),
            "amount": st.column_config.NumberColumn("amount (₹)", min_value=0.0, format="%.2f"),
            "date": st.column_config.TextColumn(help="YYYY-MM-DD"),
        })
    try:
        st.session_state.clean = normalize_expenses(edited, ids)
    except ValueError as err:
        st.error(f"Fix this before the other pages will use your edits: {err}")
    clean = st.session_state.clean
    st.download_button("Download expenses CSV", clean.to_csv(index=False), "expenses.csv", "text/csv")
    month = month_picker("exp_month")
    if month:
        s = summarize(filter_month(clean, month), card_names())
        x, y, z = st.columns(3)
        x.metric("Total", inr(s["total"]))
        y.metric("Actual", inr(s["actual"]))
        z.metric("Planned", inr(s["planned"]))
        st.subheader("By category")
        st.dataframe(s["by_category"], hide_index=True, width="stretch")
        st.subheader("By card")
        st.dataframe(s["by_card"], hide_index=True, width="stretch")


def page_compare():
    st.header("Card comparison")
    st.warning("Fictional sample cards. Enter a purchase you already plan to make; RewardWise never suggests extra spending.")
    st.caption("Which card is best for ONE purchase? Milestone-aware, but it cannot see your other planned expenses "
               "(use Monthly allocation for the month-wide trade-off).")
    cards = st.session_state.cards
    month = month_picker("cmp_month")
    prior = prior_spend_from_actuals(cards, filter_month(st.session_state.clean, month)) if month else {}
    a, b = st.columns(2)
    category = a.selectbox("Category", CATEGORIES, index=CATEGORIES.index("shopping"))
    amount = b.number_input("Purchase amount (₹)", min_value=1.0, value=7000.0, step=500.0)
    ranked = rank_cards_for_expense(cards, {"category": category, "amount": amount}, prior)
    top = ranked[0]
    st.success(f"Best for this purchase on its own: **{top['card']}**, estimated {inr(top['total_value'], 2)} "
               f"({inr(top['direct_value'], 2)} direct + {inr(top['milestone_bonus'], 2)} milestone).")
    table = pd.DataFrame([{"Rank": r["rank"], "Card": r["card"], "Direct reward": money(r["direct_value"]),
                           "Milestone bonus": money(r["milestone_bonus"]), "Total": money(r["total_value"]),
                           "Why": r["explanation"]} for r in ranked])
    st.table(table.set_index("Rank"))
    st.caption("Immediate Benefit and milestone bonuses are shown separately so nothing is counted twice. "
               "Point values are estimates. Next: open 'Monthly allocation' to see whether the whole-month plan agrees.")


def page_allocation():
    st.header("Monthly allocation recommendation")
    st.info(f"{FICTIONAL}\n\n{NO_EXTRA_SPEND} Card fees and interest are ignored.")
    month = month_picker("alloc_month")
    if month is None:
        st.info("No expenses yet.")
        return
    cards = st.session_state.cards
    with st.expander("Spend already made outside the tracker (optional)"):
        st.caption("Added to the actual spend found in your expenses, for milestone progress only.")
        extra = {c["id"]: st.number_input(f"Extra eligible spend on {c['name']} (₹)", min_value=0.0, step=1000.0, key=f"extra_{c['id']}")
                 for c in cards if c.get("milestone")}
    df, planned, prior, best, base = compute_plan(month, extra)

    st.subheader("1. What is already spent (actual)")
    actual = df[df["status"] == "actual"][["date", "description", "category", "amount", "card"]]
    if actual.empty:
        st.caption("No actual expenses this month.")
    else:
        st.dataframe(actual.rename(columns={"amount": "amount (₹)"}), hide_index=True, width="stretch")
        st.caption("Actual expenses are fixed. They only count as milestone progress; they are never re-assigned.")
    if not planned:
        st.warning("No planned expenses this month, so there is nothing to allocate.")
        return

    strategies = strategy_comparison(cards, planned, best, prior)
    plan_row = strategies[2]
    st.subheader("2. Estimated rewards for the recommended plan")
    a, b, c_ = st.columns(3)
    a.metric("Immediate Benefit (reward + discount + points + other)", money(best["immediate_benefit"]))
    b.metric("Milestone Bonus (vouchers)", money(plan_row["milestone"]))
    c_.metric("Final Score", money(plan_row["total"]))
    st.caption("Planned expenses only. Immediate Benefit and the milestone bonus are counted separately, so nothing is counted twice. "
               "RewardWise does not simply pick the highest reward-rate card.")
    (st.info if best["exact"] else st.warning)(best["method"])

    st.markdown("**How the plan compares with simpler strategies on the same planned expenses**")
    st.table(pd.DataFrame([{"Strategy": r["strategy"], "Immediate Benefit": money(r["direct"]), "Milestone vouchers": money(r["milestone"]),
                            "Total": money(r["total"]), "How it chooses": r["how"]} for r in strategies]).set_index("Strategy"))
    st.caption(f"The whole-month plan is {money(plan_row['total'] - strategies[0]['total'])} above A and "
               f"{money(plan_row['total'] - strategies[1]['total'])} above B. A ignores vouchers. B sees vouchers but cannot look ahead, "
               "so it takes the voucher with the first purchase that crosses the target. C compares complete plans. "
               "'Best' means best under this rule model.")

    st.subheader("3. Why this plan")
    for line in plan_story(cards, planned, best, prior):
        st.markdown(f"- {line}")

    st.subheader("4. Card for each planned expense")
    notes = explain_plan(cards, planned, best, prior)
    table = pd.DataFrame([{"Date": e["date"], "Expense": e["description"], "Category": e["category"], "Amount (₹)": e["amount"],
                           "Status": "planned", "Recommended card": r["card"], "Reward (₹)": r["reward_value"],
                           "Discount (₹)": r["discount_value"], "Points value (₹)": r["points_value"],
                           "Other benefits (₹)": r["other_benefit_value"] + r["unitemised_value"], "Total Benefit (₹)": r["total_benefit"]}
                          for e, r in zip(planned, best["rows"])])
    st.dataframe(table, hide_index=True, width="stretch")
    st.markdown("**Why each recommendation**")
    for x in notes:
        with st.container(border=True):
            st.markdown(f"**{x['headline']}**  \n{x['value_line']}")
            for reason in x["reasons"]:
                st.markdown(f"- {reason}")

    st.subheader("5. Milestone progress: current, projected, remaining")
    for card in cards:
        if card.get("milestone"):
            milestone_panel(card, prior, best["summary"][card["id"]])
    st.markdown("**Benefit by card (recommended plan)**")
    st.dataframe(pd.DataFrame([{"Card": card["name"], "Planned spend allocated (₹)": best["summary"][card["id"]]["allocated_spend"],
                                "Reward (₹)": best["summary"][card["id"]]["reward_value"], "Immediate Benefit (₹)": best["summary"][card["id"]]["immediate_benefit"],
                                "Reward units": f"{best['summary'][card['id']]['reward_units']:,.0f} "
                                                + ("points" if card["reward_type"] == "points" else "₹ cashback")}
                               for card in cards]), hide_index=True, width="stretch")
    legend()
    export = table.assign(**{"Why": [" ".join(x["reasons"]) for x in notes], "Data": "fictional sample rules"})
    st.download_button("Download allocation CSV", export.to_csv(index=False), f"rewardwise_allocation_{month}.csv", "text/csv")
    st.caption("Estimates use fictional rules; 'optimal' is relative to this rule model only.")


def page_scenarios():
    st.header("Scenario Walkthroughs (Part 1 & 2)")
    st.info(
        "**Demonstration Scenario Model:** These interactive walkthroughs execute the finalized presentation scenario fixtures "
        "through the RewardWise engine using the **one-expense-per-card** slide model."
    )

    part = st.radio(
        "Select Scenario Part",
        ["Part 1: Total Benefit vs Reward Ratio", "Part 2: Milestone Trade-Offs & Search Groups"],
        horizontal=True,
    )

    if part == "Part 1: Total Benefit vs Reward Ratio":
        part1_scenarios = {
            "part1_s1": "Scenario 1: Same reward ratio, better discount and benefits",
            "part1_s2": "Scenario 2: Lower reward, but benefits outweigh it",
            "part1_s3": "Scenario 3: Higher reward wins",
        }
        selected = st.selectbox(
            "Select Scenario",
            list(part1_scenarios.keys()),
            format_func=lambda k: part1_scenarios[k],
        )
        s = load_scenario(selected)
        cards = s["cards"]
        exp = s["expenses"][0]
        card_map = {c["id"]: c for c in cards}
        cand_card = card_map.get("C", cards[0])
        rival_id = s.get("rival_card", "A")
        rival_card = card_map.get(rival_id, cards[1])

        cand_benefit = reward_for_expense(cand_card, exp)
        rival_benefit = reward_for_expense(rival_card, exp)
        diff = round(cand_benefit["total_benefit"] - rival_benefit["total_benefit"], 2)

        st.subheader(f"Part 1 — {s['title']}")
        if s.get("rule"):
            st.caption(f"Rule: {s['rule']}")

        st.markdown(
            f"**Evaluated Expense:** {exp.get('description', exp.get('id', 'Purchase'))} "
            f"(`{exp['category'].title()}`) — **{inr(exp['amount'])}**"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Candidate: {cand_card['name']} Total Benefit", money(cand_benefit["total_benefit"]))
        c2.metric(f"Rival: {rival_card['name']} Total Benefit", money(rival_benefit["total_benefit"]))
        c3.metric("Difference", f"+{money(diff)}", delta=f"{money(diff)} advantage")

        st.markdown("**Benefit Breakdown Comparison**")
        cand_other = cand_benefit["other_benefit_value"] + cand_benefit.get("unitemised_value", 0.0)
        rival_other = rival_benefit["other_benefit_value"] + rival_benefit.get("unitemised_value", 0.0)
        table = pd.DataFrame([
            {"Component": "Reward (Cashback/Points Rate)", f"Candidate ({cand_card['name']})": money(cand_benefit["value"]), f"Rival ({rival_card['name']})": money(rival_benefit["value"])},
            {"Component": "Discount", f"Candidate ({cand_card['name']})": money(cand_benefit["discount_value"]), f"Rival ({rival_card['name']})": money(rival_benefit["discount_value"])},
            {"Component": "Points Value", f"Candidate ({cand_card['name']})": money(cand_benefit["points_value"]), f"Rival ({rival_card['name']})": money(rival_benefit["points_value"])},
            {"Component": "Other Benefits", f"Candidate ({cand_card['name']})": money(cand_other), f"Rival ({rival_card['name']})": money(rival_other)},
            {"Component": "Total Benefit", f"Candidate ({cand_card['name']})": money(cand_benefit["total_benefit"]), f"Rival ({rival_card['name']})": money(rival_benefit["total_benefit"])},
        ])
        st.table(table.set_index("Component"))

        st.success(
            f"**Takeaway:** Total Benefit = Reward + Discount + Points Value + Other Benefits. "
            f"**{cand_card['name']}** wins with a Total Benefit of **{money(cand_benefit['total_benefit'])}** "
            f"vs **{rival_card['name']}**'s **{money(rival_benefit['total_benefit'])}** (an advantage of **+{money(diff)}**). "
            "Reward ratio alone does not dictate card choice."
        )

    else:
        part2_scenarios = {
            "part2_s1": "Scenario 1: Lower ratio accepted for the milestone",
            "part2_s2": "Scenario 2: Ratio stays about the same",
            "part2_s3": "Scenario 3: Groups introduced: Group 3 pairing replaces a Group 1 pairing",
            "part2_s4": "Scenario 4: Groups introduced: high-reward pairing in Group 3",
            "part2_s5": "Scenario 5: Groups introduced: higher reward pairing in Group 3",
        }
        selected = st.selectbox(
            "Select Scenario",
            list(part2_scenarios.keys()),
            format_func=lambda k: part2_scenarios[k],
        )
        s = load_scenario(selected)
        cards, expenses = s["cards"], s["expenses"]
        card_map = {c["id"]: c for c in cards}

        res = solve_part2(cards, expenses)
        report = res["report"]
        base_alloc = res["baseline_allocation"]
        final_alloc = res["final_allocation"]

        st.subheader(f"Part 2 — {s['title']}")

        # Milestone/Goal definition banner
        milestone_cards = [c for c in cards if c.get("milestone")]
        for c in milestone_cards:
            m = c["milestone"]
            cat_info = f" on {', '.join(m['eligible_categories'])}" if m.get("eligible_categories") else ""
            st.info(f"🎯 **Milestone Goal:** **{c['name']}** awards a **{inr(m['voucher_value'])} voucher** once eligible spend reaches **{inr(m['eligible_spend'])}**{cat_info}.")

        # Metrics row
        st.markdown("**Optimization Score Summary**")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Baseline Immediate Benefit", money(report["baseline_score"]))
        m2.metric(
            "Revised Immediate Benefit",
            money(report["new_immediate_benefit"]),
            delta=f"-{money(report['immediate_benefit_lost'])}" if report["immediate_benefit_lost"] > 0 else None,
            delta_color="inverse",
        )
        m3.metric("Milestone Bonus", money(report["milestone_bonus"]))
        m4.metric("Final Score", money(report["final_score"]))
        m5.metric("Net Gain", f"+{money(report['net_gain'])}", delta=f"{money(report['net_gain'])} net")

        # Reallocation Dynamics Callout
        with st.container(border=True):
            st.markdown("**Milestone Reallocation Dynamics**")
            d1, d2 = st.columns(2)
            if report.get("trigger"):
                trig_eid = report["trigger"]["expense"]
                trig_cid = report["trigger"]["card"]
                trig_cname = card_map.get(trig_cid, {}).get("name", f"Card {trig_cid}")
                d1.markdown(f"**Milestone Trigger:** `{trig_eid}` forced onto **{trig_cname}** (crosses spend target)")
            else:
                d1.markdown("**Milestone Trigger:** None")

            if report.get("displaced"):
                disp_strs = [
                    f"`{d['expense']}` (was on **{card_map.get(d['was_on'], {}).get('name', d['was_on'])}**, "
                    f"re-evaluated → **{card_map.get(d['now_on'], {}).get('name', d['now_on']) if d['now_on'] else 'Next Group'}**)"
                    for d in report["displaced"]
                ]
                d2.markdown(f"**Displaced Expense(s):** {'; '.join(disp_strs)}")
            else:
                d2.markdown("**Displaced Expense(s):** None")

        # Allocation Table
        st.markdown("**Allocation Comparison (One-Expense-Per-Card Model)**")
        alloc_rows = []
        for i, exp in enumerate(expenses):
            eid = exp.get("id", f"E{i+1}")
            b_cid = base_alloc[i] if i < len(base_alloc) else None
            f_cid = final_alloc[i] if i < len(final_alloc) else None

            b_cname = card_map[b_cid]["name"] if b_cid in card_map else "—"
            f_cname = card_map[f_cid]["name"] if f_cid in card_map else "—"

            b_benefit = reward_for_expense(card_map[b_cid], exp)["total_benefit"] if b_cid in card_map else 0.0
            f_benefit = reward_for_expense(card_map[f_cid], exp)["total_benefit"] if f_cid in card_map else 0.0

            if report.get("trigger") and report["trigger"]["expense"] == eid:
                status = "⭐ Milestone Trigger"
            elif any(d["expense"] == eid for d in report.get("displaced", [])):
                status = "🔄 Displaced & Reallocated"
            elif b_cid != f_cid:
                status = "Changed"
            elif b_cid is not None:
                status = "Retained"
            else:
                status = "Unallocated"

            alloc_rows.append({
                "Expense": f"{eid}: {exp.get('description', '')}",
                "Category": exp["category"].title(),
                "Amount": inr(exp["amount"]),
                "Baseline Card": b_cname,
                "Baseline Benefit": money(b_benefit) if b_cid else "—",
                "Revised Card": f_cname,
                "Revised Benefit": money(f_benefit) if f_cid else "—",
                "Role / Change": status,
            })
        st.dataframe(pd.DataFrame(alloc_rows), hide_index=True, width="stretch")

        # Plain language explanation
        st.markdown("**Why the Allocation Changed:**")
        trig_desc = f"`{report['trigger']['expense']}` is assigned to **{card_map.get(report['trigger']['card'], {}).get('name', 'Card ' + str(report['trigger']['card']))}**" if report.get("trigger") else "An expense is reassigned"
        disp_desc = f", displacing `{', '.join(d['expense'] for d in report['displaced'])}` which is re-evaluated" if report.get("displaced") else ""
        st.markdown(
            f"- Baseline optimization achieved an Immediate Benefit of **{money(report['baseline_immediate_benefit'])}** without considering milestone bonuses.\n"
            f"- To unlock the **{money(report['milestone_bonus'])}** milestone voucher, {trig_desc}{disp_desc}.\n"
            f"- Immediate Benefit drops by **{money(report['immediate_benefit_lost'])}** (from {money(report['baseline_immediate_benefit'])} to {money(report['new_immediate_benefit'])}), "
            f"but adding the **{money(report['milestone_bonus'])}** milestone bonus produces a **Final Score of {money(report['final_score'])}**.\n"
            f"- **Verdict:** **Accepted** — resulting in a **Net Gain of +{money(report['net_gain'])}**."
        )

        # Search Groups Breakdown
        st.markdown("**Search Groups Breakdown (One-Slot-Per-Card Model)**")
        st.caption("Group 1 is the best one-slot allocation (baseline). Group 2 is the best one-slot allocation over the remaining expenses, and Group 3 over the remainder.")
        grp_data = []
        for g in res.get("groups", []):
            pairs_str = ", ".join([f"{p[0]} → Card {p[1]}" for p in g.get("pairs", [])])
            grp_data.append({
                "Group": f"Group {g['group']}",
                "Allocated Pairings": pairs_str,
                "Group Immediate Benefit": money(g["total"]),
                "Permutations Evaluated": f"{g['ways_tried']:,}",
            })
        st.table(pd.DataFrame(grp_data).set_index("Group"))

        # Collapsible full cards & expenses list
        with st.expander("View Scenario Cards & Planned Expenses", expanded=False):
            col_c, col_e = st.columns(2)
            with col_c:
                st.markdown("**Cards**")
                st.dataframe(pd.DataFrame([{
                    "Card": c["name"],
                    "Reward Type": c["reward_type"].title(),
                    "Milestone": f"{inr(c['milestone']['voucher_value'])} at {inr(c['milestone']['eligible_spend'])}" if c.get("milestone") else "None"
                } for c in cards]), hide_index=True, width="stretch")
            with col_e:
                st.markdown("**Planned Expenses**")
                st.dataframe(pd.DataFrame([{
                    "ID": e.get("id", f"E{i+1}"),
                    "Description": e.get("description", ""),
                    "Category": e.get("category", "").title(),
                    "Amount": inr(e.get("amount", 0))
                } for i, e in enumerate(expenses)]), hide_index=True, width="stretch")


# ----------------------------------------------------------------------------- main
init_state()
st.title("💳 RewardWise")
st.caption("Goal-oriented credit card rewards optimization | fictional sample cards | educational prototype")
page = st.sidebar.radio("Navigate", PAGES)
st.sidebar.warning(FICTIONAL)
{"Dashboard": page_dashboard, "Credit card portfolio": page_portfolio, "Expenses": page_expenses,
 "Card comparison": page_compare, "Monthly allocation": page_allocation,
 "Scenario Walkthroughs (Part 1 & 2)": page_scenarios}[page]()
