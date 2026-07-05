from __future__ import annotations

import pytest

from ads_agent.budget import calculate_google_ads_split
from ads_agent.google_ads_client import MockGoogleAdsClient
from ads_agent.guardrails import GuardrailError, validate_plan_for_paused_creation
from ads_agent.planner import generate_campaign_plan
from ads_agent.schemas import CampaignStatus


def test_budget_split_preserves_mmm_google_ads_proportions() -> None:
    split = calculate_google_ads_split(100)

    assert split.search_daily_budget == 56.39
    assert split.pmax_daily_budget == 43.61
    assert split.search_daily_budget + split.pmax_daily_budget == 100


def test_demo_planner_generates_search_and_pmax_plan() -> None:
    plan = generate_campaign_plan(
        business_name="Anonymized Retailer",
        total_daily_budget=100,
        landing_page_url="https://example.com",
        product_category="retail products",
        offer="seasonal value offers",
        geo_target="United States",
        language="English",
    )

    assert len(plan.campaigns) == 2
    assert {campaign.campaign_type.value for campaign in plan.campaigns} == {
        "SEARCH",
        "PERFORMANCE_MAX",
    }
    assert all(campaign.status == CampaignStatus.PAUSED for campaign in plan.campaigns)


def test_guardrail_rejects_budget_over_cap() -> None:
    plan = generate_campaign_plan(
        business_name="Anonymized Retailer",
        total_daily_budget=100,
        landing_page_url="https://example.com",
        product_category="retail products",
        offer="seasonal value offers",
        geo_target="United States",
        language="English",
    )

    with pytest.raises(GuardrailError):
        validate_plan_for_paused_creation(plan, max_daily_budget=50)


def test_mock_client_logs_paused_creation() -> None:
    plan = generate_campaign_plan(
        business_name="Anonymized Retailer",
        total_daily_budget=100,
        landing_page_url="https://example.com",
        product_category="retail products",
        offer="seasonal value offers",
        geo_target="United States",
        language="English",
    )

    result = MockGoogleAdsClient().create_paused_campaigns(plan, max_daily_budget=100)

    assert result.mode == "mock"
    assert result.success is True
    assert all(op["status"] == "PAUSED" for op in result.operations)
