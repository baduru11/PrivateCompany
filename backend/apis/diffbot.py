"""Diffbot Knowledge Graph API integration for structured company data."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_DIFFBOT_KG_URL = "https://kg.diffbot.com/kg/v3/dql"
_TIMEOUT = 30.0


def lookup_company_sync(company_name: str) -> dict[str, Any] | None:
    """Query Diffbot KG for structured company data (synchronous).

    Returns a dict with normalized fields compatible with CompanyProfile,
    or None on error / empty result.
    """
    settings = get_settings()
    api_key = settings.diffbot_api_key
    if not api_key:
        logger.debug("DIFFBOT_API_KEY not set, skipping Diffbot lookup")
        return None

    dql = f'type:Organization name:"{company_name}" sortBy:importance'
    params = {"token": api_key, "query": dql, "size": 1}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(_DIFFBOT_KG_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Diffbot lookup failed for %s: %s", company_name, exc)
        return None

    entities = data.get("data", [])
    if not entities:
        logger.debug("Diffbot returned no results for %s", company_name)
        return None

    entity = entities[0].get("entity", {})
    return _map_entity(entity)


def _map_entity(entity: dict) -> dict[str, Any]:
    """Map Diffbot entity fields to CompanyProfile-compatible dict."""
    result: dict[str, Any] = {}

    # Basic info
    if desc := entity.get("description"):
        result["description"] = desc
    if loc := entity.get("location"):
        if isinstance(loc, dict):
            parts = [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")]
            result["headquarters"] = ", ".join(p for p in parts if p)
        elif isinstance(loc, str):
            result["headquarters"] = loc
    if website := entity.get("homepageUri"):
        result["website"] = website
    if founded := entity.get("foundedDate"):
        if isinstance(founded, dict):
            result["founding_year"] = founded.get("year")
        elif isinstance(founded, str) and len(founded) >= 4:
            try:
                result["founding_year"] = int(founded[:4])
            except ValueError:
                pass

    # Employee count
    nb_employees = entity.get("nbEmployees")
    if nb_employees is not None:
        try:
            count = int(nb_employees)
            result["headcount_estimate"] = f"~{count}"
            result["employee_count_history"] = [
                {"date": date.today().strftime("%Y-%m"), "count": count, "source": "diffbot"}
            ]
        except (ValueError, TypeError):
            pass

    # Revenue
    revenues = entity.get("revenue") or entity.get("yearlyRevenues") or []
    if revenues:
        rev = revenues[0] if isinstance(revenues, list) else revenues
        if isinstance(rev, dict):
            amount = rev.get("value") or rev.get("amount")
            currency = rev.get("currency", "USD")
            if amount is not None:
                result["revenue_estimate"] = {
                    "range": _format_currency(amount, currency),
                    "source": "diffbot",
                }

    # Operating status
    if entity.get("isDissolved"):
        result["operating_status"] = "Closed"
    elif entity.get("ipo"):
        result["operating_status"] = "IPO"
    else:
        result["operating_status"] = "Active"

    # Categories / sub-sector
    categories = entity.get("categories") or []
    if categories:
        if isinstance(categories[0], dict):
            result["sub_sector"] = categories[0].get("name", "")
        else:
            result["sub_sector"] = str(categories[0])

    return result


def _format_currency(amount: float | int | str, currency: str = "USD") -> str:
    """Format a numeric amount into a human-readable currency string."""
    try:
        val = float(amount)
    except (ValueError, TypeError):
        return str(amount)

    symbol = "$" if currency == "USD" else f"{currency} "
    if val >= 1_000_000_000:
        return f"{symbol}{val / 1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"{symbol}{val / 1_000_000:.0f}M"
    if val >= 1_000:
        return f"{symbol}{val / 1_000:.0f}K"
    return f"{symbol}{val:.0f}"
