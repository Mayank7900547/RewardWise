import json

import pandas as pd
import pytest

from rewardwise.data import load_cards, normalize_expenses, validate_cards


def base_card(**kw):
    return {"id": "x", "name": "X", "reward_type": "cashback", "base_rate": 0.01, **kw}


def test_sample_cards_load_and_are_fictional(all_cards):
    assert 3 <= len(all_cards) <= 8 and all(c["fictional"] for c in all_cards)


def test_defaults_are_applied():
    c = validate_cards([base_card()])[0]
    assert c["monthly_reward_cap"] is None and c["min_transaction"] == 0 and c["excluded_categories"] == []


@pytest.mark.parametrize("bad", [
    {"base_rate": -0.1}, {"base_rate": float("nan")}, {"reward_type": "miles"},
    {"category_rates": {"spaceships": 0.1}}, {"excluded_categories": ["nope"]},
    {"milestone": {"eligible_spend": 0, "voucher_value": 10}}, {"monthly_reward_cap": -5},
    {"reward_type": "points", "point_value": 0},
])
def test_invalid_cards_rejected(bad):
    with pytest.raises(ValueError):
        validate_cards([base_card(**bad)])


def test_duplicate_ids_and_empty_list_rejected():
    with pytest.raises(ValueError):
        validate_cards([base_card(), base_card()])
    with pytest.raises(ValueError):
        validate_cards([])


def test_load_cards_from_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps([base_card()]), encoding="utf-8")
    assert load_cards(p)[0]["id"] == "x"


def frame(**kw):
    row = {"date": "2026-09-10", "description": "d", "category": "dining", "amount": 100, "status": "planned", "card": ""}
    return pd.DataFrame([{**row, **kw}])


def test_valid_expense_is_normalized():
    out = normalize_expenses(frame(category=" Dining ", status="ACTUAL"), ["a"])
    assert out.loc[0, "category"] == "dining" and out.loc[0, "status"] == "actual"
    assert out.loc[0, "date"] == "2026-09-10"


@pytest.mark.parametrize("bad", [
    {"amount": -1}, {"amount": 0}, {"amount": float("nan")}, {"amount": float("inf")}, {"amount": "abc"},
    {"category": "spaceships"}, {"status": "maybe"}, {"date": "not a date"}, {"date": None}, {"card": "ghost"},
])
def test_invalid_expenses_rejected(bad):
    with pytest.raises(ValueError):
        normalize_expenses(frame(**bad), ["a"])


def test_blank_rows_dropped_and_missing_columns_defaulted():
    df = pd.DataFrame({"date": ["2026-09-01", None], "category": ["fuel", None], "amount": [50, None]})
    out = normalize_expenses(df)
    assert len(out) == 1 and out.loc[0, "status"] == "planned" and out.loc[0, "card"] == ""


def test_empty_input_gives_empty_typed_frame():
    out = normalize_expenses(pd.DataFrame())
    assert out.empty and list(out.columns) == ["date", "description", "category", "amount", "status", "card"]


def test_error_message_names_the_row():
    df = pd.concat([frame(), frame(amount=-5)], ignore_index=True)
    with pytest.raises(ValueError, match="row 2"):
        normalize_expenses(df)
