"""Utility functions for data cleaning and deduplication."""
from __future__ import annotations
from backend.models import FundingRound
import re


def deduplicate_funding_rounds(rounds: list[FundingRound]) -> list[FundingRound]:
    """Deduplicate funding rounds by matching on amount + stage.

    If two rounds have the same parsed amount and same stage,
    keep the one with the more specific date.
    """
    if not rounds:
        return rounds

    def _parse_amount(amt: str | None) -> float:
        if not amt:
            return 0
        m = re.match(r"\$?\s*~?\s*([\d,.]+)\s*(T|B|M|K)?", amt, re.IGNORECASE)
        if not m:
            return 0
        num = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").upper()
        multipliers = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}
        return num * multipliers.get(suffix, 1)

    def _date_specificity(d: str | None) -> int:
        if not d:
            return 0
        return len(d)

    seen: dict[str, FundingRound] = {}
    for r in rounds:
        amt = _parse_amount(r.amount)
        key = f"{amt:.0f}_{(r.stage or '').lower().strip()}"
        if key in seen:
            existing = seen[key]
            if _date_specificity(r.date) > _date_specificity(existing.date):
                seen[key] = r
        else:
            seen[key] = r

    return list(seen.values())
