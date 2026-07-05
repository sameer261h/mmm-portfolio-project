"""Phase 2 read-only analyst tools.

Each function below is one "tool" the analyst agent (ads_agent/analyst_agent.py)
can call. They are read-only by design -- Phase 2 is explicitly the zero-risk
phase in GOOGLE_ADS_AGENT_PLAN.md. Nothing here can create, pause, enable, or
change a budget; that is Phase 3, gated on human approval.

Backed by ads_agent/analyst_data.py's deterministic mock data until Phase 0's
Basic access is approved and a real read-only Ads API call replaces it. The
return shapes here are written to match what the real API would give us, so
swapping the implementation later shouldn't change any caller.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from ads_agent.analyst_data import (
    MOCK_CAMPAIGNS,
    MOCK_SEARCH_TERMS,
    generate_daily_performance,
)
from ads_agent.operator_state import get_campaign_overrides


def _effective_budget(campaign) -> float:
    """Base mock budget, overridden by any Phase 3 approved change."""

    return get_campaign_overrides(campaign.id).get("daily_budget", campaign.daily_budget)


def _effective_status(campaign) -> str:
    """Base mock status, overridden by any Phase 3 approved change."""

    return get_campaign_overrides(campaign.id).get("status", campaign.status)


def list_campaigns() -> list[dict[str, object]]:
    """Return every campaign in the account with its type, status, and budget."""

    return [
        {
            "id": campaign.id,
            "name": campaign.name,
            "campaign_type": campaign.campaign_type,
            "status": _effective_status(campaign),
            "daily_budget": _effective_budget(campaign),
        }
        for campaign in MOCK_CAMPAIGNS
    ]


def get_performance(date_range_days: int = 14) -> list[dict[str, object]]:
    """Return daily impressions/clicks/cost/conversions/CPA/CTR for the window."""

    rows = generate_daily_performance(days=date_range_days)
    return [
        {
            "campaign_id": row.campaign_id,
            "date": row.date.isoformat(),
            "impressions": row.impressions,
            "clicks": row.clicks,
            "cost": row.cost,
            "conversions": row.conversions,
            "cpa": row.cpa,
            "ctr": row.ctr,
        }
        for row in rows
    ]


def get_search_terms(campaign_id: str | None = None) -> list[dict[str, object]]:
    """Return search-term performance, optionally filtered to one campaign.

    Terms added as negative keywords via an approved Phase 3 change are
    excluded -- they've been told to stop matching, so they shouldn't keep
    showing up as "wasting spend" in later analyst answers.
    """

    terms = MOCK_SEARCH_TERMS
    if campaign_id:
        terms = [term for term in terms if term.campaign_id == campaign_id]

    # Broad-match-style word-boundary check, not exact string equality -- a
    # negative keyword "free" should block the search term "free retail
    # products" the same way it would in a real account, without also
    # blocking unrelated terms that merely contain "free" as a substring.
    negative_keywords_by_campaign = {
        campaign.id: set(get_campaign_overrides(campaign.id).get("negative_keywords", []))
        for campaign in MOCK_CAMPAIGNS
    }
    terms = [
        term
        for term in terms
        if not any(
            re.search(rf"\b{re.escape(negative)}\b", term.term, re.IGNORECASE)
            for negative in negative_keywords_by_campaign.get(term.campaign_id, set())
        )
    ]

    return [
        {
            "campaign_id": term.campaign_id,
            "term": term.term,
            "clicks": term.clicks,
            "cost": term.cost,
            "conversions": term.conversions,
            "cpa": round(term.cost / term.conversions, 2) if term.conversions else None,
        }
        for term in terms
    ]


def get_budget_pacing() -> list[dict[str, object]]:
    """Return month-to-date spend vs. budget pacing per campaign."""

    today = date.today()
    days_elapsed = today.day
    next_month = date(today.year + (today.month == 12), (today.month % 12) + 1, 1)
    days_in_month = (next_month - timedelta(days=1)).day

    rows = generate_daily_performance(days=days_elapsed)
    pacing: list[dict[str, object]] = []
    for campaign in MOCK_CAMPAIGNS:
        daily_budget = _effective_budget(campaign)
        spend_so_far = round(sum(row.cost for row in rows if row.campaign_id == campaign.id), 2)
        expected_spend = round(daily_budget * days_elapsed, 2)
        projected_month_spend = round(daily_budget * days_in_month, 2)
        pacing.append(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "daily_budget": daily_budget,
                "days_elapsed_this_month": days_elapsed,
                "spend_so_far": spend_so_far,
                "expected_spend_at_budget": expected_spend,
                "pacing_pct": round(spend_so_far / expected_spend * 100, 1) if expected_spend else 0.0,
                "projected_month_spend": projected_month_spend,
            }
        )
    return pacing


# OpenAI function-calling schemas, one per tool above. Keep names in sync with
# TOOL_FUNCTIONS below -- the agent calls tools by matching these names.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "list_campaigns",
        "description": "List every campaign in the account with type, status, and daily budget.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "get_performance",
        "description": (
            "Get daily impressions, clicks, cost, conversions, CPA, and CTR for the "
            "last N days, across all campaigns."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date_range_days": {
                    "type": "integer",
                    "description": "How many trailing days to include. Defaults to 14.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_search_terms",
        "description": (
            "Get search-term-level performance (clicks, cost, conversions, CPA), "
            "optionally filtered to one campaign_id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Optional campaign id to filter to.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_budget_pacing",
        "description": "Get month-to-date spend vs. budget pacing per campaign.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

TOOL_FUNCTIONS = {
    "list_campaigns": list_campaigns,
    "get_performance": get_performance,
    "get_search_terms": get_search_terms,
    "get_budget_pacing": get_budget_pacing,
}
