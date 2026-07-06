"""Apply one approved ChangeTicket via the mock/real Google Ads client.

Extracted out of streamlit_app.py so both the live UI (Phase 3's manual
request and Phase 5's simulated loop) and ads_agent/evals.py's offline
harness can approve a ticket through the exact same code path, without the
harness needing to import streamlit_app.py itself (which would execute the
whole Streamlit page at import time outside of a real Streamlit run).
"""

from __future__ import annotations

import re

from ads_agent.analyst_tools import list_campaigns
from ads_agent.google_ads_client import AdsOperationResult, get_ads_client
from ads_agent.schemas import ChangeAction, ChangeTicket


def apply_change_ticket(ticket: ChangeTicket, max_daily_budget: float) -> AdsOperationResult:
    """Apply an approved ticket. Raises GuardrailError/RuntimeError/NotImplementedError
    on any guardrail failure -- callers are expected to catch those."""

    client = get_ads_client()
    if ticket.action == ChangeAction.UPDATE_BUDGET:
        current = next(c for c in list_campaigns() if c["id"] == ticket.campaign_id)
        new_budget = float(re.sub(r"[^0-9.]", "", ticket.proposed_value))
        return client.update_campaign_budget(
            campaign_id=ticket.campaign_id,
            campaign_name=ticket.campaign_name,
            current_daily_budget=current["daily_budget"],
            new_daily_budget=new_budget,
            max_daily_budget=max_daily_budget,
        )
    if ticket.action == ChangeAction.PAUSE_CAMPAIGN:
        return client.pause_campaign(campaign_id=ticket.campaign_id, campaign_name=ticket.campaign_name)
    return client.add_negative_keyword(
        campaign_id=ticket.campaign_id,
        campaign_name=ticket.campaign_name,
        keyword_text=ticket.proposed_value,
    )
