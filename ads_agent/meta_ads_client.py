"""Mock and real Meta (Facebook/Instagram) Ads connectors.

Mirrors ads_agent/google_ads_client.py's Mock/Real split exactly. The mock
connector is the default and is what runs whenever META_ADS_MUTATE_ENABLED
is not exactly "true". The real connector talks to Meta's Marketing API via
the facebook-business SDK -- built against the documented API shape, but
UNVERIFIED: Sameer has no Meta Business Manager / developer App / Ad
Account set up yet as of 2026-07-05, so none of this has been run against a
real account. Treat every RealMetaAdsClient method as best-effort correct
until it's been run once for real and any errors ironed out -- see
META_ADS_AGENT_PLAN.md for the setup checklist and status.

Unlike Google Ads, Meta has no free "test account" -- the safety model here
is structural, not account-based: campaigns/ad sets/ads are always created
PAUSED, enable is never implemented, and billing is never touched.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from ads_agent.audit import write_audit_event
from ads_agent.guardrails import validate_meta_enable_request, validate_meta_plan_for_paused_creation
from ads_agent.meta_schemas import MetaCampaignPlan


@dataclass
class AdsOperationResult:
    mode: str
    success: bool
    message: str
    operations: list[dict[str, object]]


class MetaAdsClient(Protocol):
    def create_paused_campaigns(self, plan: MetaCampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        ...

    def enable_campaigns(self, plan: MetaCampaignPlan) -> AdsOperationResult:
        ...


class MockMetaAdsClient:
    """Logs what would happen without touching Meta's API."""

    def create_paused_campaigns(self, plan: MetaCampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        validate_meta_plan_for_paused_creation(plan, max_daily_budget=max_daily_budget)
        operations = [
            {
                "action": "CREATE_PAUSED_CAMPAIGN",
                "platform": "META",
                "objective": campaign.objective.value,
                "name": campaign.name,
                "daily_budget": campaign.daily_budget,
                "status": campaign.status.value,
            }
            for campaign in plan.campaigns
        ]
        write_audit_event("meta_mock_create_paused_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="mock",
            success=True,
            message="Mock Meta campaigns created as paused audit-log entries.",
            operations=operations,
        )

    def enable_campaigns(self, plan: MetaCampaignPlan) -> AdsOperationResult:
        validate_meta_enable_request(plan)
        operations = [
            {"action": "ENABLE_CAMPAIGN_AFTER_APPROVAL", "platform": "META", "name": campaign.name}
            for campaign in plan.campaigns
        ]
        write_audit_event("meta_mock_enable_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="mock",
            success=True,
            message="Mock Meta campaigns enabled in the audit log only.",
            operations=operations,
        )


def _init_meta_api() -> None:
    """Initialize the facebook-business SDK from .env credentials."""

    from facebook_business.api import FacebookAdsApi

    FacebookAdsApi.init(
        app_id=os.environ["META_ADS_APP_ID"],
        app_secret=os.environ["META_ADS_APP_SECRET"],
        access_token=os.environ["META_ADS_ACCESS_TOKEN"],
    )


class RealMetaAdsClient:
    """Live Meta Marketing API mutation. UNVERIFIED as of 2026-07-05 --
    Sameer has no Business Manager / App / Ad Account yet, so none of this
    has actually been run. Built as correctly as possible from Meta's
    documented Marketing API shape; expect to need a debugging pass once
    real credentials exist, the same way Google Ads Phase 4 did."""

    def __init__(self) -> None:
        if os.getenv("META_ADS_MUTATE_ENABLED", "false").lower() != "true":
            raise RuntimeError("Real Meta Ads mutation is disabled.")
        self._ad_account_id = os.environ["META_ADS_AD_ACCOUNT_ID"]
        self._page_id = os.environ["META_ADS_PAGE_ID"]

    def create_paused_campaigns(self, plan: MetaCampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        validate_meta_plan_for_paused_creation(plan, max_daily_budget=max_daily_budget)

        from ads_agent.meta_ads_builders import create_meta_campaign_from_draft

        _init_meta_api()
        operations = [
            create_meta_campaign_from_draft(self._ad_account_id, self._page_id, campaign)
            for campaign in plan.campaigns
        ]
        write_audit_event("meta_real_create_paused_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="real",
            success=True,
            message="Meta campaigns created as PAUSED.",
            operations=operations,
        )

    def enable_campaigns(self, plan: MetaCampaignPlan) -> AdsOperationResult:
        validate_meta_enable_request(plan)
        raise NotImplementedError(
            "Real Meta campaign enablement is intentionally blocked -- "
            "enabling lets a campaign start spending and serving, which is "
            "out of scope until this has been reviewed with Sameer."
        )


def get_meta_ads_client() -> MetaAdsClient:
    """Return the safe connector unless live mutation is explicitly enabled."""

    if os.getenv("META_ADS_MUTATE_ENABLED", "false").lower() == "true":
        return RealMetaAdsClient()
    return MockMetaAdsClient()
