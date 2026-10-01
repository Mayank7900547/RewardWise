"""Loading and validation of card rules (JSON) and expenses (CSV / DataFrame).

Validation lives here so every other module can assume clean input.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

CATEGORIES = ("groceries", "shopping", "dining", "fuel", "travel", "utilities", "other")
STATUSES = ("planned", "actual")
REWARD_TYPES = ("cashback", "points")
EXPENSE_COLUMNS = ["date", "description", "category", "amount", "status", "card"]


# --------------------------------------------------------------------------- cards
def _number(value, label, minimum=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return float(value)


def _check_categories(cats, label):
    if cats is None:
        return None
    bad = [c for c in cats if c not in CATEGORIES]
    if bad:
        raise ValueError(f"{label} contains unsupported categories: {bad}")
    return list(cats)


def _discount_rule(rule, cid):
    label = f"card {cid}: discount_rules"
    out = {"categories": _check_categories(rule.get("categories"), label),
           "rate": _number(rule.get("rate", 0), f"{label}.rate"), "flat": _number(rule.get("flat", 0), f"{label}.flat"),
           "min_transaction": _number(rule.get("min_transaction", 0), f"{label}.min_transaction"), "max_discount": None}
    if rule.get("max_discount") is not None:
        out["max_discount"] = _number(rule["max_discount"], f"{label}.max_discount")
    return out


def _bonus_points(bp, cid):
    if not bp:
        return None
    label = f"card {cid}: bonus_points"
    out = {"per_100": _number(bp.get("per_100", 0), f"{label}.per_100"),
           "categories": _check_categories(bp.get("categories"), label)}
    if bp.get("point_value") is not None:
        out["point_value"] = _number(bp["point_value"], f"{label}.point_value")
    return out


def _other_benefit(b, cid):
    label = f"card {cid}: other_benefits"
    return {"name": str(b.get("name", "Other benefit")), "value": _number(b.get("value", 0), f"{label}.value"),
            "categories": _check_categories(b.get("categories"), label),
            "min_transaction": _number(b.get("min_transaction", 0), f"{label}.min_transaction")}


def validate_cards(cards: list[dict]) -> list[dict]:
    """Validate card rules and return copies with every optional field defaulted."""
    if not isinstance(cards, list) or not cards:
        raise ValueError("cards must be a non-empty list")
    seen, clean = set(), []
    for raw in cards:
        for key in ("id", "name", "reward_type", "base_rate"):
            if key not in raw:
                raise ValueError(f"card {raw.get('id', '?')!r} is missing required field '{key}'")
        cid = raw["id"]
        if cid in seen:
            raise ValueError(f"duplicate card id: {cid}")
        seen.add(cid)
        if raw["reward_type"] not in REWARD_TYPES:
            raise ValueError(f"card {cid}: reward_type must be one of {REWARD_TYPES}")
        card = {
            "issuer": "", "eligible_categories": None, "excluded_categories": [],
            "min_transaction": 0.0, "monthly_reward_cap": None, "point_value": 1.0,
            "reward_balance": 0.0, "milestone": None, "fictional": True, **raw,
        }
        card["base_rate"] = _number(card["base_rate"], f"card {cid}: base_rate")
        card["category_rates"] = {}
        for cat, rate in raw.get("category_rates", {}).items():
            if cat not in CATEGORIES:
                raise ValueError(f"card {cid}: unsupported category in category_rates: {cat}")
            card["category_rates"][cat] = _number(rate, f"card {cid}: rate for {cat}")
        card["eligible_categories"] = _check_categories(card["eligible_categories"], f"card {cid}: eligible_categories")
        card["excluded_categories"] = _check_categories(card["excluded_categories"], f"card {cid}: excluded_categories")
        card["min_transaction"] = _number(card["min_transaction"], f"card {cid}: min_transaction")
        card["point_value"] = _number(card["point_value"], f"card {cid}: point_value")
        if card["reward_type"] == "points" and card["point_value"] <= 0:
            raise ValueError(f"card {cid}: point_value must be > 0 for points cards")
        if card["monthly_reward_cap"] is not None:
            card["monthly_reward_cap"] = _number(card["monthly_reward_cap"], f"card {cid}: monthly_reward_cap")
        card["reward_balance"] = _number(card["reward_balance"], f"card {cid}: reward_balance")
        card["discount_rules"] = [_discount_rule(r, cid) for r in raw.get("discount_rules") or []]
        card["bonus_points"] = _bonus_points(raw.get("bonus_points"), cid)
        card["other_benefits"] = [_other_benefit(b, cid) for b in raw.get("other_benefits") or []]
        m = card["milestone"]
        if m:
            m = dict(m)
            m["eligible_spend"] = _number(m.get("eligible_spend"), f"card {cid}: milestone.eligible_spend")
            if m["eligible_spend"] <= 0:
                raise ValueError(f"card {cid}: milestone.eligible_spend must be > 0")
            m["voucher_value"] = _number(m.get("voucher_value"), f"card {cid}: milestone.voucher_value")
            m["eligible_categories"] = _check_categories(m.get("eligible_categories"), f"card {cid}: milestone.eligible_categories")
            m.setdefault("period", "monthly")
            m.setdefault("name", "Milestone voucher")
            card["milestone"] = m
        clean.append(card)
    return clean


def load_cards(path) -> list[dict]:
    return validate_cards(json.loads(Path(path).read_text(encoding="utf-8")))


# ------------------------------------------------------------------------ expenses
def _is_blank(value) -> bool:
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() in ("", "None", "nan", "NaT")


def _text(series: pd.Series) -> pd.Series:
    return series.map(lambda v: "" if _is_blank(v) else str(v).strip())


def empty_expenses() -> pd.DataFrame:
    return pd.DataFrame({"date": pd.Series(dtype="object"), "description": pd.Series(dtype="object"),
                         "category": pd.Series(dtype="object"), "amount": pd.Series(dtype="float64"),
                         "status": pd.Series(dtype="object"), "card": pd.Series(dtype="object")})


def normalize_expenses(df: pd.DataFrame, valid_card_ids=None) -> pd.DataFrame:
    """Validate and clean an expense table. Raises ValueError listing the bad rows.

    - fully blank rows (e.g. added but left empty in the editor) are dropped
    - amount must be a finite number > 0 (NaN and inf are rejected)
    - category must be supported; status defaults to 'planned'
    - date must parse; it is stored as an ISO string (YYYY-MM-DD)
    - card is optional, but if given it must be a known card id
    """
    df = df.copy()
    for col in EXPENSE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[EXPENSE_COLUMNS]
    keep = [not all(_is_blank(v) for v in row) for row in df.itertuples(index=False)]
    df = df[keep].reset_index(drop=True)
    if df.empty:
        return empty_expenses()

    out = pd.DataFrame(index=df.index)
    errors: list[str] = []

    def flag(mask, message):
        for i in df.index[mask]:
            errors.append(f"row {i + 1}: {message}")

    dates = pd.to_datetime(_text(df["date"]).replace("", None), errors="coerce")
    flag(dates.isna(), "date is missing or not a valid date (use YYYY-MM-DD)")
    out["date"] = dates.dt.strftime("%Y-%m-%d")
    out["description"] = _text(df["description"])
    out["category"] = _text(df["category"]).str.lower()
    flag(~out["category"].isin(CATEGORIES), f"category must be one of {', '.join(CATEGORIES)}")
    amount = pd.to_numeric(df["amount"], errors="coerce")
    flag(amount.isna() | ~amount.map(lambda v: math.isfinite(v) if pd.notna(v) else False), "amount must be a finite number")
    flag(amount.notna() & (amount <= 0), "amount must be greater than 0")
    out["amount"] = amount.astype(float)
    out["status"] = _text(df["status"]).str.lower().replace("", "planned")
    flag(~out["status"].isin(STATUSES), "status must be 'planned' or 'actual'")
    out["card"] = _text(df["card"])
    if valid_card_ids is not None:
        flag((out["card"] != "") & ~out["card"].isin(list(valid_card_ids)), "card is not a known card id")
    if errors:
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        raise ValueError("; ".join(errors[:5]) + more)
    return out[EXPENSE_COLUMNS].reset_index(drop=True)


def load_expenses(path, valid_card_ids=None) -> pd.DataFrame:
    return normalize_expenses(pd.read_csv(path), valid_card_ids)
