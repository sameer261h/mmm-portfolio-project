"""Mock and real Google Ads connectors.

The mock connector is the default portfolio path and is what runs whenever
GOOGLE_ADS_MUTATE_ENABLED is not exactly "true" (the default). The real
connector talks to the actual Google Ads API -- CONFIRMED WORKING (2026-07-05):
verified live against a real Google Ads test account, including both Search
and Performance Max paused campaign creation. See HANDOFF.md's status log
for the real bugs found and fixed along the way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from ads_agent.audit import write_audit_event
from ads_agent.guardrails import (
    GuardrailError,
    check_daily_write_rate_limit,
    validate_action_allowed,
    validate_budget_change,
    validate_enable_request,
    validate_plan_for_paused_creation,
)
from ads_agent.operator_state import (
    apply_budget_override,
    apply_negative_keyword,
    apply_pause_override,
)
from ads_agent.schemas import CampaignPlan


@dataclass
class AdsOperationResult:
    mode: str
    success: bool
    message: str
    operations: list[dict[str, object]]


class AdsClient(Protocol):
    def create_paused_campaigns(self, plan: CampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        ...

    def enable_campaigns(self, plan: CampaignPlan) -> AdsOperationResult:
        ...

    def update_campaign_budget(
        self, campaign_id: str, campaign_name: str, current_daily_budget: float,
        new_daily_budget: float, max_daily_budget: float,
    ) -> AdsOperationResult:
        ...

    def pause_campaign(self, campaign_id: str, campaign_name: str) -> AdsOperationResult:
        ...

    def add_negative_keyword(
        self, campaign_id: str, campaign_name: str, keyword_text: str
    ) -> AdsOperationResult:
        ...


class MockGoogleAdsClient:
    """Logs what would happen without touching Google Ads."""

    def create_paused_campaigns(self, plan: CampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        validate_plan_for_paused_creation(plan, max_daily_budget=max_daily_budget)
        operations = [
            {
                "action": "CREATE_PAUSED_CAMPAIGN",
                "campaign_type": campaign.campaign_type.value,
                "name": campaign.name,
                "daily_budget": campaign.daily_budget,
                "status": campaign.status.value,
            }
            for campaign in plan.campaigns
        ]
        write_audit_event("mock_create_paused_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="mock",
            success=True,
            message="Mock campaigns created as paused audit-log entries.",
            operations=operations,
        )

    def enable_campaigns(self, plan: CampaignPlan) -> AdsOperationResult:
        validate_enable_request(plan)
        operations = [
            {
                "action": "ENABLE_CAMPAIGN_AFTER_APPROVAL",
                "campaign_type": campaign.campaign_type.value,
                "name": campaign.name,
            }
            for campaign in plan.campaigns
        ]
        write_audit_event("mock_enable_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="mock",
            success=True,
            message="Mock campaigns enabled in the audit log only.",
            operations=operations,
        )

    def update_campaign_budget(
        self, campaign_id: str, campaign_name: str, current_daily_budget: float,
        new_daily_budget: float, max_daily_budget: float,
    ) -> AdsOperationResult:
        validate_action_allowed("UPDATE_BUDGET")
        validate_budget_change(current_daily_budget, new_daily_budget, max_daily_budget)
        check_daily_write_rate_limit()

        new_daily_budget = round(new_daily_budget, 2)
        apply_budget_override(campaign_id, new_daily_budget)
        operation = {
            "action": "UPDATE_BUDGET",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "previous_daily_budget": current_daily_budget,
            "new_daily_budget": new_daily_budget,
        }
        write_audit_event("operator_change_applied", operation)
        return AdsOperationResult(
            mode="mock",
            success=True,
            message=f"{campaign_name}: daily budget updated to ${new_daily_budget:,.2f}.",
            operations=[operation],
        )

    def pause_campaign(self, campaign_id: str, campaign_name: str) -> AdsOperationResult:
        validate_action_allowed("PAUSE_CAMPAIGN")
        check_daily_write_rate_limit()

        apply_pause_override(campaign_id)
        operation = {
            "action": "PAUSE_CAMPAIGN",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
        }
        write_audit_event("operator_change_applied", operation)
        return AdsOperationResult(
            mode="mock",
            success=True,
            message=f"{campaign_name} paused.",
            operations=[operation],
        )

    def add_negative_keyword(
        self, campaign_id: str, campaign_name: str, keyword_text: str
    ) -> AdsOperationResult:
        validate_action_allowed("ADD_NEGATIVE_KEYWORD")
        check_daily_write_rate_limit()

        apply_negative_keyword(campaign_id, keyword_text)
        operation = {
            "action": "ADD_NEGATIVE_KEYWORD",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "keyword_text": keyword_text,
        }
        write_audit_event("operator_change_applied", operation)
        return AdsOperationResult(
            mode="mock",
            success=True,
            message=f'"{keyword_text}" added as a negative keyword on {campaign_name}.',
            operations=[operation],
        )


def _build_googleads_client():
    """Construct a real GoogleAdsClient from the .env / Secret Manager credentials."""

    from google.ads.googleads.client import GoogleAdsClient

    credentials = {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"],
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(credentials)


class RealGoogleAdsClient:
    """Live Google Ads mutation. CONFIRMED WORKING (2026-07-05) against a
    real Google Ads test account -- see HANDOFF.md's status log for the
    real bugs found and fixed during live verification."""

    def __init__(self) -> None:
        if os.getenv("GOOGLE_ADS_MUTATE_ENABLED", "false").lower() != "true":
            raise RuntimeError("Real Google Ads mutation is disabled.")
        self._customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"]

    def create_paused_campaigns(self, plan: CampaignPlan, max_daily_budget: float) -> AdsOperationResult:
        validate_plan_for_paused_creation(plan, max_daily_budget=max_daily_budget)

        from ads_agent.google_ads_builders import create_campaign_from_draft

        client = _build_googleads_client()
        operations = [
            create_campaign_from_draft(client, self._customer_id, campaign, business_name=plan.business_name)
            for campaign in plan.campaigns
        ]
        write_audit_event("real_create_paused_campaigns", {"operations": operations})
        return AdsOperationResult(
            mode="real",
            success=True,
            message="Campaigns created as PAUSED in the test account.",
            operations=operations,
        )

    def enable_campaigns(self, plan: CampaignPlan) -> AdsOperationResult:
        validate_enable_request(plan)
        raise NotImplementedError(
            "Real campaign enablement is intentionally blocked for v1 -- "
            "enabling a campaign lets it start spending real (test) budget "
            "and serving, which is out of scope until this has been "
            "reviewed with Sameer."
        )

    def update_campaign_budget(
        self, campaign_id: str, campaign_name: str, current_daily_budget: float,
        new_daily_budget: float, max_daily_budget: float,
    ) -> AdsOperationResult:
        validate_action_allowed("UPDATE_BUDGET")
        validate_budget_change(current_daily_budget, new_daily_budget, max_daily_budget)
        check_daily_write_rate_limit()
        new_daily_budget = round(new_daily_budget, 2)

        from google.ads.googleads.errors import GoogleAdsException
        from google.protobuf import field_mask_pb2

        client = _build_googleads_client()
        ga_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT campaign.campaign_budget FROM campaign "
            f"WHERE campaign.id = {campaign_id}"
        )
        try:
            rows = list(ga_service.search(customer_id=self._customer_id, query=query))
            if not rows:
                raise GuardrailError(f"Campaign {campaign_id} not found in the account.")
            budget_resource_name = rows[0].campaign.campaign_budget

            budget_service = client.get_service("CampaignBudgetService")
            operation = client.get_type("CampaignBudgetOperation")
            budget = operation.update
            budget.resource_name = budget_resource_name
            budget.amount_micros = int(new_daily_budget * 1_000_000)
            client.copy_from(
                operation.update_mask,
                field_mask_pb2.FieldMask(paths=["amount_micros"]),
            )
            budget_service.mutate_campaign_budgets(
                customer_id=self._customer_id, operations=[operation]
            )
        except GoogleAdsException as exc:
            raise RuntimeError(f"Google Ads API error updating budget: {exc}") from exc

        operation_log = {
            "action": "UPDATE_BUDGET",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "previous_daily_budget": current_daily_budget,
            "new_daily_budget": new_daily_budget,
        }
        write_audit_event("operator_change_applied", operation_log)
        return AdsOperationResult(
            mode="real",
            success=True,
            message=f"{campaign_name}: daily budget updated to ${new_daily_budget:,.2f} (live).",
            operations=[operation_log],
        )

    def pause_campaign(self, campaign_id: str, campaign_name: str) -> AdsOperationResult:
        validate_action_allowed("PAUSE_CAMPAIGN")
        check_daily_write_rate_limit()

        from google.ads.googleads.errors import GoogleAdsException
        from google.protobuf import field_mask_pb2

        client = _build_googleads_client()
        campaign_service = client.get_service("CampaignService")
        try:
            operation = client.get_type("CampaignOperation")
            campaign = operation.update
            campaign.resource_name = campaign_service.campaign_path(self._customer_id, campaign_id)
            campaign.status = client.enums.CampaignStatusEnum.PAUSED
            client.copy_from(
                operation.update_mask, field_mask_pb2.FieldMask(paths=["status"])
            )
            campaign_service.mutate_campaigns(
                customer_id=self._customer_id, operations=[operation]
            )
        except GoogleAdsException as exc:
            raise RuntimeError(f"Google Ads API error pausing campaign: {exc}") from exc

        operation_log = {
            "action": "PAUSE_CAMPAIGN",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
        }
        write_audit_event("operator_change_applied", operation_log)
        return AdsOperationResult(
            mode="real",
            success=True,
            message=f"{campaign_name} paused (live).",
            operations=[operation_log],
        )

    def add_negative_keyword(
        self, campaign_id: str, campaign_name: str, keyword_text: str
    ) -> AdsOperationResult:
        validate_action_allowed("ADD_NEGATIVE_KEYWORD")
        check_daily_write_rate_limit()

        from google.ads.googleads.errors import GoogleAdsException

        client = _build_googleads_client()
        campaign_service = client.get_service("CampaignService")
        criterion_service = client.get_service("CampaignCriterionService")
        try:
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_service.campaign_path(self._customer_id, campaign_id)
            criterion.negative = True
            criterion.keyword.text = keyword_text
            criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
            criterion_service.mutate_campaign_criteria(
                customer_id=self._customer_id, operations=[operation]
            )
        except GoogleAdsException as exc:
            raise RuntimeError(f"Google Ads API error adding negative keyword: {exc}") from exc

        operation_log = {
            "action": "ADD_NEGATIVE_KEYWORD",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "keyword_text": keyword_text,
        }
        write_audit_event("operator_change_applied", operation_log)
        return AdsOperationResult(
            mode="real",
            success=True,
            message=f'"{keyword_text}" added as a negative keyword on {campaign_name} (live).',
            operations=[operation_log],
        )


def get_ads_client() -> AdsClient:
    """Return the safe connector unless live mutation is explicitly enabled."""

    if os.getenv("GOOGLE_ADS_MUTATE_ENABLED", "false").lower() == "true":
        return RealGoogleAdsClient()
    return MockGoogleAdsClient()
