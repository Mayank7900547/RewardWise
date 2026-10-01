import pandas as pd

from rewardwise.data import load_expenses, normalize_expenses
from rewardwise.tracker import (available_months, filter_month, planned_expenses,
                                prior_spend_from_actuals, summarize)


def table(rows):
    return normalize_expenses(pd.DataFrame(rows, columns=["date", "description", "category", "amount", "status", "card"]))


ROWS = [
    ["2026-09-06", "tv", "shopping", 15000, "actual", "milestone"],
    ["2026-09-27", "food", "groceries", 8000, "planned", ""],
    ["2026-09-28", "shoes", "shopping", 7000, "planned", ""],
    ["2026-10-02", "fuel", "fuel", 1000, "planned", ""],
]


def test_summary_totals_and_breakdowns():
    s = summarize(table(ROWS))
    assert (s["planned"], s["actual"], s["total"]) == (16000, 15000, 31000)
    cat = s["by_category"].set_index("category")
    assert cat.loc["shopping", "total"] == 22000 and cat.loc["shopping", "planned"] == 7000
    assert s["by_card"].set_index("card").loc["milestone", "actual"] == 15000


def test_month_helpers():
    df = table(ROWS)
    assert available_months(df) == ["2026-09", "2026-10"]
    assert len(filter_month(df, "2026-09")) == 3


def test_empty_summary_does_not_crash():
    s = summarize(table([]))
    assert s["total"] == 0 and s["by_category"].empty and s["by_card"].empty


def test_prior_spend_counts_actuals_only_and_respects_exclusions(all_cards):
    df = table(ROWS + [["2026-09-07", "petrol", "fuel", 4000, "actual", "milestone"]])
    assert prior_spend_from_actuals(all_cards, df) == {"milestone": 15000.0}  # fuel excluded, planned ignored


def test_planned_expenses_only_planned():
    assert len(planned_expenses(table(ROWS))) == 3


def test_sample_csv_matches_the_brief_scenario(all_cards):
    from conftest import ROOT
    df = load_expenses(ROOT / "data/expenses.csv", [c["id"] for c in all_cards])
    assert summarize(df)["planned"] == 30000
    assert prior_spend_from_actuals(all_cards, df) == {"milestone": 15000.0}
