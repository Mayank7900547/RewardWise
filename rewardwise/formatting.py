"""Small display helpers (kept out of the engines so they stay pure)."""
from __future__ import annotations


def inr(value: float, decimals: int = 0) -> str:
    """Format a number as rupees using Indian digit grouping, e.g. ₹1,00,000."""
    sign = "-" if value < 0 else ""
    whole, _, frac = f"{abs(value):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}" + (f".{frac}" if frac else "")


def money(value: float) -> str:
    """Like inr() but drops the paise for whole rupees: 350 -> ₹350, 350.5 -> ₹350.50."""
    return inr(value, 0) if abs(value - round(value)) < 0.005 else inr(value, 2)
