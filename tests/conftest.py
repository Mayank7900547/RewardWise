"""Shared fixtures. Tests use the three cards from the project brief (A, B, C) so they do
not break when someone edits the extra sample cards in data/cards.json."""
from pathlib import Path

import pytest

from rewardwise.data import load_cards

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def all_cards():
    return load_cards(ROOT / "data/cards.json")


@pytest.fixture(scope="session")
def cards(all_cards):
    """Card A (5% online shopping cashback), B (5 pts/₹100 groceries), C (₹1,000 voucher at ₹20,000)."""
    return [c for c in all_cards if c["id"] in ("shopping", "grocery", "milestone")]


def exp(category, amount, **kw):
    return {"category": category, "amount": float(amount), **kw}
