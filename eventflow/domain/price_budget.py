from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal


_FREE_LABELS = re.compile(r"\b(free|complimentary|rsvp|n/a|na)\b", re.I)


def parse_price_to_minor_units(price: str | None) -> int | None:
    """
    Best-effort parse of human-readable ticket lines into integer minor units (e.g. cents).

    Ambiguous international formats are interpreted pragmatically: we take the last plausible
    decimal number in the string. Returns None when no amount can be inferred (caller may exclude from totals).
    """
    if price is None:
        return None
    s = price.strip()
    if not s:
        return None
    if _FREE_LABELS.search(s) or s.replace(" ", "").lower() in {"$0", "$0.00", "0", "0.00"}:
        return 0
    # Pull numeric tokens (handles "25", "25.00", "1.234,56" poorly — strip letters/currency symbols first).
    nums = re.findall(r"\d+(?:[.,]\d+)?", s)
    if not nums:
        return None
    raw = nums[-1]
    # Prefer explicit decimal: last separator decides fractional vs thousands heuristically.
    if "," in raw and "." in raw:
        # Assume comma thousands if dot is decimal (US): "1,234.56"
        if raw.rfind(".") > raw.rfind(","):
            normalized = raw.replace(",", "")
        else:
            normalized = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts[-1]) == 2 and parts[-1].isdigit():
            normalized = ".".join(parts[:-1]) + "." + parts[-1]
        else:
            normalized = raw.replace(",", "")
    else:
        normalized = raw
    try:
        dec = Decimal(normalized)
    except Exception:
        return None
    minor = int((dec * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return minor


def budget_band(*, spent_minor: int, budget_minor: int | None) -> str:
    """Semantic labels for UI: unset | under | tight | over."""
    if budget_minor is None or budget_minor <= 0:
        return "unset"
    if spent_minor > budget_minor:
        return "over"
    # Within budget but close (top 15% of range feels "tight").
    if spent_minor > int(budget_minor * 0.85):
        return "tight"
    return "under"
