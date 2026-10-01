"""Monthly expense tracker: pandas summaries over a validated expense table."""
from __future__ import annotations

import pandas as pd

from .goals import milestone_counts


def available_months(df: pd.DataFrame) -> list[str]:
    """Months present in the data as 'YYYY-MM', oldest first."""
    return sorted(df["date"].str[:7].unique().tolist()) if not df.empty else []


def filter_month(df: pd.DataFrame, month: str) -> pd.DataFrame:
    return df[df["date"].str.startswith(month)].reset_index(drop=True)


def _by(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[key, "planned", "actual", "total"])
    table = (df.pivot_table(index=key, columns="status", values="amount", aggfunc="sum", fill_value=0.0)
               .reindex(columns=["planned", "actual"], fill_value=0.0))
    table["total"] = table["planned"] + table["actual"]
    return table.sort_values("total", ascending=False).reset_index()


def summarize(df: pd.DataFrame, card_names: dict | None = None) -> dict:
    """Totals plus category-wise and card-wise spending (planned / actual / total)."""
    planned = float(df.loc[df["status"] == "planned", "amount"].sum())
    actual = float(df.loc[df["status"] == "actual", "amount"].sum())
    by_card = _by(df[df["card"] != ""], "card")
    if card_names and not by_card.empty:
        by_card.insert(1, "card_name", by_card["card"].map(card_names).fillna(by_card["card"]))
    return {"planned": planned, "actual": actual, "total": planned + actual,
            "by_category": _by(df, "category"), "by_card": by_card, "count": int(len(df))}


def planned_expenses(df: pd.DataFrame) -> list[dict]:
    """Planned rows as plain dicts for the allocation engine."""
    return df[df["status"] == "planned"].to_dict("records")


def prior_spend_from_actuals(cards: list[dict], df: pd.DataFrame) -> dict:
    """Milestone-eligible spend already made (status 'actual') on each milestone card.

    This is how "I've already spent ₹15,000 on Card C" enters the engine: as history that
    counts towards progress, never as a new expense.
    """
    prior = {}
    actual = df[df["status"] == "actual"]
    for card in cards:
        if card.get("milestone"):
            rows = actual[actual["card"] == card["id"]].to_dict("records")
            prior[card["id"]] = float(sum(r["amount"] for r in rows if milestone_counts(card, r)))
    return prior
