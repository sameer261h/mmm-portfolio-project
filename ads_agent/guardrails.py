"""Hard safety checks that do not rely on the LLM behaving well."""

from __future__ import annotations

from datetime import datetime, timezone

from ads_agent.audit import read_audit_events
from ads_agent.schemas import CampaignPlan, CampaignStatus, CampaignType

# Phase 3 write guardrails. These are deliberately hardcoded, not
# LLM-configurable -- the whole point is that a misbehaving or manipulated
# agent still can't get past them.
MAX_BUDGET_CHANGE_PCT = 0.50
MAX_WRITES_PER_DAY = 20

# The only write actions Phase 3 ever exposes to the agent. There is no
# delete or payment tool anywhere in this codebase for it to be tricked into
# calling -- the allowlist below is a second, defense-in-depth check on top
# of that.
ALLOWED_WRITE_ACTIONS = {"UPDATE_BUDGET", "PAUSE_CAMPAIGN", "ADD_NEGATIVE_KEYWORD"}


class GuardrailError(ValueError):
    """Raised when a campaign plan violates a non-negotiable safety rule."""


def validate_plan_for_paused_creation(plan: CampaignPlan, max_daily_budget: float) -> None:
    """Validate that a plan is safe to create as paused Google Ads campaigns."""

    if plan.total_daily_budget <= 0:
        raise GuardrailError("Total daily budget must be greater than 0.")
    if plan.total_daily_budget > max_daily_budget:
        raise GuardrailError(
            f"Total daily budget ${plan.total_daily_budget:,.2f} exceeds "
            f"the configured cap of ${max_daily_budget:,.2f}."
        )

    planned_budget = sum(campaign.daily_budget for campaign in plan.campaigns)
    if abs(planned_budget - plan.total_daily_budget) > 0.05:
        raise GuardrailError(
            "Campaign budgets must add up to the approved total daily budget."
        )

    for campaign in plan.campaigns:
        if campaign.status != CampaignStatus.PAUSED:
            raise GuardrailError("Campaigns must be created in PAUSED status.")
        if "delete" in campaign.name.lower():
            raise GuardrailError("Delete-style operations are not allowed.")
        if campaign.campaign_type == CampaignType.PERFORMANCE_MAX:
            missing_assets = not campaign.pmax_assets or not campaign.pmax_assets.headlines
            if missing_assets:
                raise GuardrailError("PMax campaign is missing required asset drafts.")


def validate_enable_request(plan: CampaignPlan) -> None:
    """Validate the separate approval step before enabling campaigns."""

    if not plan.campaigns:
        raise GuardrailError("No campaigns are available to enable.")


def validate_action_allowed(action: str) -> None:
    """Reject any write action that isn't on the hardcoded allowlist."""

    if action not in ALLOWED_WRITE_ACTIONS:
        raise GuardrailError(
            f"Action '{action}' is not on the allowlist of permitted write actions."
        )


def validate_budget_change(
    current_budget: float, new_budget: float, max_daily_budget: float
) -> None:
    """Enforce a per-change budget cap and a per-change percentage-move cap.

    The percentage cap exists so a single approved change can't swing a
    campaign's spend wildly -- large reallocations must go through multiple
    smaller approved steps instead of one big jump.
    """

    if new_budget <= 0:
        raise GuardrailError("New daily budget must be greater than 0.")
    if new_budget > max_daily_budget:
        raise GuardrailError(
            f"New daily budget ${new_budget:,.2f} exceeds the configured cap "
            f"of ${max_daily_budget:,.2f}."
        )

    change_pct = abs(new_budget - current_budget) / current_budget if current_budget else 1.0
    if change_pct > MAX_BUDGET_CHANGE_PCT:
        raise GuardrailError(
            f"Budget change of {change_pct:.0%} exceeds the "
            f"{MAX_BUDGET_CHANGE_PCT:.0%} per-change cap. Split large "
            "reallocations into smaller approved steps."
        )


def check_daily_write_rate_limit() -> None:
    """Raise if today's approved-write count has hit the daily cap.

    Counts from the audit log itself rather than a separate counter, so the
    limit can't be reset by anything other than the day rolling over.
    """

    today = datetime.now(timezone.utc).date().isoformat()
    applied_today = [
        event
        for event in read_audit_events(event_type="operator_change_applied")
        if event["timestamp"].startswith(today)
    ]
    if len(applied_today) >= MAX_WRITES_PER_DAY:
        raise GuardrailError(
            f"Daily write limit of {MAX_WRITES_PER_DAY} approved changes has "
            "been reached. Try again tomorrow."
        )
