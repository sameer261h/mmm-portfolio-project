"""Campaign planning agent.

The app uses OpenAI when an API key is present. Without a key, it falls back to a
deterministic planner so the portfolio demo still works before credentials exist.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from ads_agent.budget import calculate_google_ads_split
from ads_agent.openai_schema_utils import to_openai_strict_schema
from ads_agent.schemas import (
    CampaignDraft,
    CampaignPlan,
    CampaignStatus,
    CampaignType,
    Keyword,
    PMaxAssetDraft,
    SearchAdDraft,
)


SYSTEM_PROMPT = """You are a senior Google Ads strategist.
Create campaign drafts from an MMM budget envelope.
Rules:
- Return only valid JSON matching the provided schema.
- Create exactly one Search campaign and one Performance Max campaign.
- Campaigns must be PAUSED.
- Do not invent the landing page; use the provided URL.
- Explain budget rationale, bids, keyword mix, editable parameters, and risks.
- Do not recommend delete, billing, or payment actions."""


def generate_campaign_plan(
    *,
    business_name: str,
    total_daily_budget: float,
    landing_page_url: str,
    product_category: str,
    offer: str,
    geo_target: str,
    language: str,
) -> CampaignPlan:
    """Generate a campaign plan using OpenAI when configured, else demo logic."""

    if os.getenv("OPENAI_API_KEY"):
        try:
            return _generate_with_openai(
                business_name=business_name,
                total_daily_budget=total_daily_budget,
                landing_page_url=landing_page_url,
                product_category=product_category,
                offer=offer,
                geo_target=geo_target,
                language=language,
            )
        except Exception as exc:  # pragma: no cover - safety fallback for live APIs
            return _generate_demo_plan(
                business_name=business_name,
                total_daily_budget=total_daily_budget,
                landing_page_url=landing_page_url,
                product_category=product_category,
                offer=f"{offer} (OpenAI fallback used: {exc})",
                geo_target=geo_target,
                language=language,
            )

    return _generate_demo_plan(
        business_name=business_name,
        total_daily_budget=total_daily_budget,
        landing_page_url=landing_page_url,
        product_category=product_category,
        offer=offer,
        geo_target=geo_target,
        language=language,
    )


def _generate_with_openai(**kwargs: object) -> CampaignPlan:
    """Call OpenAI with a strict JSON-schema output contract."""

    from openai import OpenAI

    split = calculate_google_ads_split(float(kwargs["total_daily_budget"]))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI()

    user_payload = {
        **kwargs,
        "budget_split": split.__dict__,
        "mmm_interpretation": (
            "MMM recommends shifting Google-controllable spend toward digital video "
            "and display while keeping search meaningful but less over-weighted. "
            "Use the manual daily budget size but preserve this digital split."
        ),
    }

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "campaign_plan",
                "schema": to_openai_strict_schema(CampaignPlan.model_json_schema()),
                "strict": True,
            }
        },
    )

    return CampaignPlan.model_validate_json(response.output_text)


def _generate_demo_plan(
    *,
    business_name: str,
    total_daily_budget: float,
    landing_page_url: str,
    product_category: str,
    offer: str,
    geo_target: str,
    language: str,
) -> CampaignPlan:
    """Deterministic campaign plan for demos, tests, and no-key environments."""

    split = calculate_google_ads_split(total_daily_budget)
    suffix = datetime.now().strftime("%Y%m%d-%H%M")
    category = product_category or "retail products"
    offer_text = offer or "current seasonal offer"

    search_campaign = CampaignDraft(
        campaign_type=CampaignType.SEARCH,
        name=f"MMM-Agent-Demo-Search-{suffix}",
        daily_budget=split.search_daily_budget,
        status=CampaignStatus.PAUSED,
        bid_strategy="Maximize conversions with conservative launch budget",
        landing_page_url=landing_page_url,
        geo_targets=[geo_target],
        languages=[language],
        rationale=(
            "Search receives the larger Google Ads share because the MMM still shows "
            "meaningful search contribution, but the constrained optimizer trims it "
            "from the historical over-weighted level. The campaign captures active "
            "demand while leaving room for PMax prospecting."
        ),
        editable_parameters=[
            "daily_budget",
            "keywords",
            "negative_keywords",
            "ad_copy",
            "geo_targets",
            "bid_strategy",
        ],
        risk_flags=[
            "Search demand may cap scale.",
            "Keyword intent must be checked before enabling.",
        ],
        keywords=[
            Keyword(text=f"buy {category}", match_type="PHRASE", rationale="Captures mid-funnel purchase intent."),
            Keyword(text=f"{category} deals", match_type="PHRASE", rationale="Matches offer-seeking shoppers."),
            Keyword(text=f"best {category}", match_type="BROAD", rationale="Expands discovery while staying category-led."),
            Keyword(text=business_name, match_type="EXACT", rationale="Protects branded demand in the demo account."),
        ],
        negative_keywords=["free", "jobs", "repair", "used"],
        search_ad=SearchAdDraft(
            headlines=[
                f"{business_name} Official Store",
                f"Shop {category.title()}",
                offer_text[:30],
                "Fast Online Shopping",
                "Explore New Arrivals",
            ],
            descriptions=[
                f"Discover {category} from {business_name}. {offer_text}",
                "Built from an MMM-led budget test. Review and approve before launch.",
            ],
        ),
    )

    pmax_campaign = CampaignDraft(
        campaign_type=CampaignType.PERFORMANCE_MAX,
        name=f"MMM-Agent-Demo-PMax-{suffix}",
        daily_budget=split.pmax_daily_budget,
        status=CampaignStatus.PAUSED,
        bid_strategy="Maximize conversion value after conversion tracking is confirmed",
        landing_page_url=landing_page_url,
        geo_targets=[geo_target],
        languages=[language],
        rationale=(
            "PMax groups the MMM's display and digital-video opportunity into one "
            "Google-executable activation layer. It is capped below Search in v1 "
            "because assets and conversion tracking must be validated before scale."
        ),
        editable_parameters=[
            "daily_budget",
            "asset_text",
            "audience_signals",
            "geo_targets",
            "bid_strategy",
        ],
        risk_flags=[
            "Real PMax launch requires image/video assets and conversion goals.",
            "Use paused status until policy and tracking checks pass.",
        ],
        pmax_assets=PMaxAssetDraft(
            headlines=[
                f"Shop {business_name}",
                f"{category.title()} Online",
                offer_text[:30],
            ],
            long_headlines=[
                f"Explore {category} from {business_name} with an MMM-guided launch budget"
            ],
            descriptions=[
                f"Find {category} selected for today’s shoppers.",
                "Campaign generated as a paused draft for human review.",
            ],
            audience_signals=[
                f"In-market: {category}",
                "Past site visitors",
                "Cart abandoners",
            ],
        ),
    )

    return CampaignPlan(
        business_name=business_name,
        total_daily_budget=split.total_daily_budget,
        landing_page_url=landing_page_url,
        mmm_summary=(
            f"Manual budget ${split.total_daily_budget:,.2f}/day is allocated using "
            f"the MMM digital envelope: {split.search_share:.1%} Search and "
            f"{split.pmax_share:.1%} PMax for display/video-style activity."
        ),
        executive_summary=(
            "Create paused Search and PMax campaigns that translate the MMM budget "
            "recommendation into Google Ads actions. The user can edit all major "
            "parameters before approving creation or enablement."
        ),
        campaigns=[search_campaign, pmax_campaign],
    )
