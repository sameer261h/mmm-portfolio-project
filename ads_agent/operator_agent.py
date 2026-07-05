"""Phase 3 operator agent: proposes write changes, never applies them.

`propose_change(request)` is the only thing this module exports, and its
return type is a ChangeTicket -- a proposal, not an action. There is no
function anywhere in this file that can create, pause, enable, or mutate a
campaign; applying an approved ticket is a separate call the Streamlit
Approve button makes directly to ads_agent/google_ads_client.py. That split
is the human-approval gate: the LLM's output can only ever become an
on-screen proposal, never a side effect.

Same "no key = demo mode" pattern as planner.py and analyst_agent.py: uses
OpenAI's structured-output mode when OPENAI_API_KEY is set, else a
deterministic keyword-routed fallback.
"""

from __future__ import annotations

import os

from ads_agent.analyst_tools import get_budget_pacing, get_search_terms, list_campaigns
from ads_agent.openai_schema_utils import to_openai_strict_schema
from ads_agent.schemas import ChangeAction, ChangeTicket

SYSTEM_PROMPT = """You are a Google Ads operator assistant.
Given a natural-language request and the current account state, propose exactly
one change as a ChangeTicket.
Rules:
- Only ever propose one of: UPDATE_BUDGET, PAUSE_CAMPAIGN, ADD_NEGATIVE_KEYWORD.
- campaign_id must be one of the campaign ids given in the account state -- never invent one.
- current_value and proposed_value are short human-readable strings (e.g. "$56.39/day", "ENABLED").
- For ADD_NEGATIVE_KEYWORD specifically, proposed_value must be EXACTLY the
  keyword text and nothing else -- e.g. "free", not "add free as a negative
  keyword" or "exclude the term free retail products". current_value should
  be "not excluded" for this action.
- reason explains why, grounded in the account state provided (not guessed).
- expected_impact is a short, honest estimate -- do not overpromise results.
- You are proposing only. You have no ability to apply this change yourself."""


def propose_change(request: str) -> ChangeTicket:
    """Propose a single change ticket for a human to approve or reject."""

    if os.getenv("OPENAI_API_KEY"):
        try:
            return _propose_with_openai(request)
        except Exception:  # pragma: no cover - safety fallback for live APIs
            return _propose_with_keywords(request)

    return _propose_with_keywords(request)


def _account_context() -> dict[str, object]:
    return {
        "campaigns": list_campaigns(),
        "budget_pacing": get_budget_pacing(),
        "search_terms": get_search_terms(),
    }


def _propose_with_openai(request: str) -> ChangeTicket:
    import json

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI()

    user_payload = {"request": request, "account_state": _account_context()}

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, default=str)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "change_ticket",
                "schema": to_openai_strict_schema(ChangeTicket.model_json_schema()),
                "strict": True,
            }
        },
    )

    return ChangeTicket.model_validate_json(response.output_text)


def _propose_with_keywords(request: str) -> ChangeTicket:
    """Deterministic fallback: route by keyword so the demo works with no key."""

    context = _account_context()
    campaigns = context["campaigns"]
    q = request.lower()

    def find_target(campaigns: list[dict[str, object]]) -> dict[str, object]:
        if any(word in q for word in ["pmax", "performance max", "performance_max"]):
            return next((c for c in campaigns if c["campaign_type"] == "PERFORMANCE_MAX"), campaigns[0])
        if "search" in q:
            return next((c for c in campaigns if c["campaign_type"] == "SEARCH"), campaigns[0])
        return next((c for c in campaigns if c["name"].lower() in q), campaigns[0])

    if "negative" in q or "waste" in q or "wasting" in q:
        search_campaign = next(c for c in campaigns if c["campaign_type"] == "SEARCH")
        search_terms = [t for t in context["search_terms"] if t["campaign_id"] == search_campaign["id"]]
        zero_conversion_terms = [t for t in search_terms if t["conversions"] == 0]
        worst = max(zero_conversion_terms, key=lambda t: t["cost"], default=None)
        if worst is None:
            worst = max(search_terms, key=lambda t: t["cpa"] or 0)
        keyword_text = worst["term"].split()[0]
        return ChangeTicket(
            action=ChangeAction.ADD_NEGATIVE_KEYWORD,
            campaign_id=search_campaign["id"],
            campaign_name=search_campaign["name"],
            current_value="not excluded",
            proposed_value=keyword_text,
            reason=f'"{worst["term"]}" spent ${worst["cost"]:.2f} with {worst["conversions"]} conversions.',
            expected_impact="Should reduce wasted spend on non-converting queries containing this word.",
        )

    if "pause" in q or "stop" in q or "turn off" in q:
        target = find_target(campaigns)
        return ChangeTicket(
            action=ChangeAction.PAUSE_CAMPAIGN,
            campaign_id=target["id"],
            campaign_name=target["name"],
            current_value=target["status"],
            proposed_value="PAUSED",
            reason="Requested pause of this campaign.",
            expected_impact="Spend on this campaign stops immediately once approved.",
        )

    # Default: budget change. Look for a campaign name/type mention and a
    # rough direction (cut vs increase) in the request text.
    target = find_target(campaigns)
    direction = -1 if any(word in q for word in ["reduce", "cut", "lower", "decrease"]) else 1
    proposed_budget = round(target["daily_budget"] * (1 + direction * 0.15), 2)
    return ChangeTicket(
        action=ChangeAction.UPDATE_BUDGET,
        campaign_id=target["id"],
        campaign_name=target["name"],
        current_value=f"${target['daily_budget']:,.2f}/day",
        proposed_value=f"${proposed_budget:,.2f}/day",
        reason="Requested budget adjustment for this campaign.",
        expected_impact="A 15% budget move should shift spend proportionally, within the per-change guardrail cap.",
    )
