"""UI-level checks with Streamlit's headless AppTest: what the person actually sees on screen."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import ROOT

PAGES = ["Dashboard", "Credit card portfolio", "Expenses", "Card comparison", "Monthly allocation"]


def open_page(page, expenses=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    if expenses is not None:                       # start from custom expenses instead of data/expenses.csv
        at.session_state["base"], at.session_state["clean"], at.session_state["version"] = expenses, expenses.copy(), 0
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metrics(at):
    return {m.label: m.value for m in at.metric}


def all_text(at):
    parts = [e.value for e in at.markdown] + [e.value for e in at.info] + [e.value for e in at.warning]
    parts += [e.value for e in at.success] + [e.value for e in at.caption]
    return "\n".join(parts)


def rows(*items):
    return pd.DataFrame(items, columns=["date", "description", "category", "amount", "status", "card"])


@pytest.mark.parametrize("page", PAGES)
def test_every_page_says_the_data_is_fictional(page):
    at = open_page(page)
    assert any("Fictional sample data" in w.value for w in at.sidebar.warning)


def test_allocation_page_separates_direct_milestone_and_progress():
    m = metrics(open_page("Monthly allocation"))
    assert m["Immediate Benefit (reward + discount + points + other)"] == "₹515"
    assert m["Milestone Bonus (vouchers)"] == "₹1,000"
    assert m["Final Score"] == "₹1,515"
    assert (m["Current (actual spend)"], m["Planned on this card"], m["Projected"], m["Remaining requirement"]) == \
           ("₹15,000", "₹6,000", "₹21,000", "₹0")


def test_dashboard_separates_actual_planned_direct_and_milestone():
    m = metrics(open_page("Dashboard"))
    assert (m["Total expenses"], m["Actual (already spent)"], m["Planned (still to come)"]) == ("₹45,000", "₹15,000", "₹30,000")
    assert (m["Immediate Benefit (reward + discount + points + other)"], m["Milestone Bonus (vouchers)"]) == ("₹515", "₹1,000")
    assert m["Final Score with recommended plan"] == "₹1,515"
    assert m["Current (actual spend)"] == "₹15,000" and m["Projected"] == "₹21,000" and m["Remaining requirement"] == "₹0"


def test_allocation_page_explains_why_card_a_keeps_the_shopping_purchase():
    text = all_text(open_page("Monthly allocation"))
    assert "Online shopping (₹7,000) → Card A — Shopping" in text
    assert "Judged on its own, Card C would look better (₹1,035 vs ₹350)" in text
    assert "lower the month's total by ₹315" in text
    assert "Exhaustive search over all 1,024 allocations" in text


def test_allocation_page_states_that_it_never_suggests_extra_spending():
    assert "never suggests spending extra" in all_text(open_page("Monthly allocation"))


def test_shortfall_is_reported_honestly_on_screen():
    at = open_page("Monthly allocation", rows(
        ("2026-09-06", "Electronics", "shopping", 15000.0, "actual", "milestone"),
        ("2026-09-29", "Fuel", "fuel", 4000.0, "planned", "")))
    text = all_text(at)
    assert metrics(at)["Remaining requirement"] == "₹5,000"
    assert "NOT reachable" in text and "will not suggest extra spending" in text
    assert any("Not reached by this plan" in w.value for w in at.warning)


def test_already_earned_voucher_is_not_counted_again_on_screen():
    at = open_page("Monthly allocation")
    at.number_input(key="extra_milestone").set_value(6000).run()
    m = metrics(at)
    assert m["Milestone Bonus (vouchers)"] == "₹0" and m["Final Score"] == "₹515"
    assert any("Already earned" in i.value for i in at.info)


def test_card_comparison_shows_card_c_first_for_a_lone_7000_shopping_purchase():
    at = open_page("Card comparison")
    assert any("Card C — Milestone" in s.value and "₹1,035" in s.value for s in at.success)
    assert "never suggests extra spending" in all_text(at)
