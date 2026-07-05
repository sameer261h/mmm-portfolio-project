from __future__ import annotations

import pytest
from pydantic import ValidationError

from ads_agent.budget import MMM_RECOMMENDED_WEEKLY_META, calculate_meta_ads_split
from ads_agent.guardrails import GuardrailError
from ads_agent.meta_ads_client import MockMetaAdsClient
from ads_agent.meta_planner import generate_meta_campaign_plan
from ads_agent.meta_schemas import (
    MetaAdCreativeDraft,
    MetaCampaignDraft,
    MetaCampaignObjective,
    MetaCampaignPlan,
)
from ads_agent.schemas import CampaignStatus


def _valid_creative() -> MetaAdCreativeDraft:
    return MetaAdCreativeDraft(
        primary_texts=["Discover retail products from Acme."],
        headlines=["Shop Acme"],
        descriptions=["Paused draft for human review."],
    )


def _valid_campaign(daily_budget: float = 50.0) -> MetaCampaignDraft:
    return MetaCampaignDraft(
        name="Test Meta Feed Campaign",
        objective=MetaCampaignObjective.OUTCOME_TRAFFIC,
        daily_budget=daily_budget,
        status=CampaignStatus.PAUSED,
        landing_page_url="https://example.com",
        rationale="Activates the MMM's social channel recommendation for this test.",
        editable_parameters=["daily_budget"],
        risk_flags=["Uses a placeholder image."],
        creative=_valid_creative(),
    )


def _valid_plan(daily_budget: float = 50.0) -> MetaCampaignPlan:
    return MetaCampaignPlan(
        business_name="Acme",
        total_daily_budget=daily_budget,
        landing_page_url="https://example.com",
        mmm_summary="Manual budget allocated to a single Meta Feed campaign.",
        executive_summary="Create one paused Meta Feed campaign for human review.",
        campaigns=[_valid_campaign(daily_budget)],
    )


# --- schemas ------------------------------------------------------------


def test_meta_campaign_draft_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MetaCampaignDraft(
            **_valid_campaign().model_dump(),
            unexpected_field="not allowed",
        )


def test_meta_campaign_plan_builds_with_one_campaign() -> None:
    plan = _valid_plan()
    assert len(plan.campaigns) == 1
    assert plan.campaigns[0].status == CampaignStatus.PAUSED


def test_meta_campaign_plan_requires_at_least_one_campaign() -> None:
    with pytest.raises(ValidationError):
        MetaCampaignPlan(
            business_name="Acme",
            total_daily_budget=50.0,
            landing_page_url="https://example.com",
            mmm_summary="Manual budget allocated to a single Meta Feed campaign.",
            executive_summary="Create one paused Meta Feed campaign for human review.",
            campaigns=[],
        )


# --- budget split ---------------------------------------------------------


def test_mmm_recommended_weekly_meta_matches_notebook_output() -> None:
    # Confirmed directly from notebooks/02_build_mmm.ipynb cell 14's optimizer
    # output -- the real recommended_weekly_$ figure for the "social" channel,
    # not a placeholder.
    assert MMM_RECOMMENDED_WEEKLY_META["social"] == 307_995.0


def test_calculate_meta_ads_split_assigns_full_budget_to_feed_campaign() -> None:
    split = calculate_meta_ads_split(100.0)
    assert split.total_daily_budget == 100.0
    assert split.feed_daily_budget == 100.0


def test_calculate_meta_ads_split_rejects_non_positive_budget() -> None:
    with pytest.raises(ValueError):
        calculate_meta_ads_split(0)


# --- MockMetaAdsClient ------------------------------------------------------


def test_create_paused_campaigns_succeeds_in_mock_mode() -> None:
    client = MockMetaAdsClient()
    result = client.create_paused_campaigns(_valid_plan(), max_daily_budget=1000)

    assert result.mode == "mock"
    assert result.success
    assert result.operations[0]["platform"] == "META"
    assert result.operations[0]["status"] == "PAUSED"


def test_create_paused_campaigns_rejects_budget_over_cap() -> None:
    client = MockMetaAdsClient()
    with pytest.raises(GuardrailError):
        client.create_paused_campaigns(_valid_plan(daily_budget=2000), max_daily_budget=1000)


def test_enable_campaigns_succeeds_in_mock_mode() -> None:
    client = MockMetaAdsClient()
    result = client.enable_campaigns(_valid_plan())

    assert result.mode == "mock"
    assert result.operations[0]["platform"] == "META"


# --- meta_planner demo-mode fallback (no OpenAI key) ------------------------


def test_generate_meta_campaign_plan_demo_fallback(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    plan = generate_meta_campaign_plan(
        business_name="Acme",
        total_daily_budget=50.0,
        landing_page_url="https://example.com",
        product_category="retail products",
        offer="seasonal offer",
        geo_target="United States",
    )

    assert len(plan.campaigns) == 1
    campaign = plan.campaigns[0]
    assert campaign.status == CampaignStatus.PAUSED
    assert campaign.daily_budget == 50.0
    assert campaign.creative.headlines
