"""Meta (Facebook/Instagram) Ads campaign planning agent.

Mirrors ads_agent/planner.py's OpenAI-with-deterministic-fallback structure,
for a single paused Meta Feed campaign instead of Google's Search + PMax
pair.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from ads_agent.budget import calculate_meta_ads_split
from ads_agent.meta_schemas import (
    MetaAdCreativeDraft,
    MetaCampaignDraft,
    MetaCampaignObjective,
    MetaCampaignPlan,
)
from ads_agent.openai_schema_utils import to_openai_strict_schema
from ads_agent.schemas import CampaignStatus


META_SYSTEM_PROMPT = """You are a senior Meta (Facebook/Instagram) Ads strategist.
Create a campaign draft from an MMM budget envelope.
Rules:
- Return only valid JSON matching the provided schema.
- Create exactly one Feed campaign with objective OUTCOME_TRAFFIC or OUTCOME_SALES.
- The campaign must be PAUSED.
- Do not invent the landing page; use the provided URL.
- Explain budget rationale, targeting, creative angle, editable parameters, and risks.
- Do not recommend delete, billing, or payment actions."""


def generate_meta_campaign_plan(
    *,
    business_name: str,
    total_daily_budget: float,
    landing_page_url: str,
    product_category: str,
    offer: str,
    geo_target: str,
) -> MetaCampaignPlan:
    """Generate a Meta campaign plan using OpenAI when configured, else demo logic."""

    if os.getenv("OPENAI_API_KEY"):
        try:
            return _generate_with_openai(
                business_name=business_name,
                total_daily_budget=total_daily_budget,
                landing_page_url=landing_page_url,
                product_category=product_category,
                offer=offer,
                geo_target=geo_target,
            )
        except Exception as exc:  # pragma: no cover - safety fallback for live APIs
            return _generate_demo_plan(
                business_name=business_name,
                total_daily_budget=total_daily_budget,
                landing_page_url=landing_page_url,
                product_category=product_category,
                offer=f"{offer} (OpenAI fallback used: {exc})",
                geo_target=geo_target,
            )

    return _generate_demo_plan(
        business_name=business_name,
        total_daily_budget=total_daily_budget,
        landing_page_url=landing_page_url,
        product_category=product_category,
        offer=offer,
        geo_target=geo_target,
    )


def _generate_with_openai(**kwargs: object) -> MetaCampaignPlan:
    """Call OpenAI with a strict JSON-schema output contract."""

    from openai import OpenAI

    split = calculate_meta_ads_split(float(kwargs["total_daily_budget"]))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI()

    user_payload = {
        **kwargs,
        "budget_split": split.__dict__,
        "mmm_interpretation": (
            "MMM recommends $307,995/week for the social channel, up 75% from "
            "current spend -- the strongest percentage increase of any channel "
            "in the plan. Treat this as genuine headroom to grow into, not a cut."
        ),
    }

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": META_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "meta_campaign_plan",
                "schema": to_openai_strict_schema(MetaCampaignPlan.model_json_schema()),
                "strict": True,
            }
        },
    )

    return MetaCampaignPlan.model_validate_json(response.output_text)


def _generate_demo_plan(
    *,
    business_name: str,
    total_daily_budget: float,
    landing_page_url: str,
    product_category: str,
    offer: str,
    geo_target: str,
) -> MetaCampaignPlan:
    """Deterministic Meta campaign plan for demos, tests, and no-key environments."""

    split = calculate_meta_ads_split(total_daily_budget)
    suffix = datetime.now().strftime("%Y%m%d-%H%M")
    category = product_category or "retail products"
    offer_text = offer or "current seasonal offer"

    feed_campaign = MetaCampaignDraft(
        name=f"MMM-Agent-Demo-Meta-Feed-{suffix}",
        objective=MetaCampaignObjective.OUTCOME_TRAFFIC,
        daily_budget=split.feed_daily_budget,
        status=CampaignStatus.PAUSED,
        landing_page_url=landing_page_url,
        geo_targets=[geo_target],
        rationale=(
            "The MMM shows social as the highest-percentage-growth opportunity "
            "in the plan (+75% vs. current weekly spend), so this campaign "
            "activates that headroom as a single, conservatively-targeted Feed "
            "campaign rather than immediately matching the full recommended "
            "weekly figure."
        ),
        editable_parameters=[
            "daily_budget",
            "creative_text",
            "geo_targets",
            "age_min",
            "age_max",
            "interests",
        ],
        risk_flags=[
            "No real creative assets -- uses a placeholder image until real creative is supplied.",
            "Interest targeting is illustrative text, not yet resolved to real Meta interest IDs.",
        ],
        creative=MetaAdCreativeDraft(
            primary_texts=[
                f"Discover {category} from {business_name}. {offer_text}",
            ],
            headlines=[
                f"Shop {business_name}",
                f"{category.title()} Online",
            ],
            descriptions=[
                "Campaign generated as a paused draft for human review.",
            ],
            call_to_action="SHOP_NOW",
        ),
    )

    return MetaCampaignPlan(
        business_name=business_name,
        total_daily_budget=split.total_daily_budget,
        landing_page_url=landing_page_url,
        mmm_summary=(
            f"Manual budget ${split.total_daily_budget:,.2f}/day is allocated to "
            "a single Meta Feed campaign, activating the MMM's `social` channel "
            "recommendation ($307,995/week, +75% vs. current) that the agentic "
            "layer previously left unused."
        ),
        executive_summary=(
            "Create one paused Meta Feed campaign that translates the MMM's "
            "social-channel budget recommendation into a Meta Ads action. "
            "The user can edit all major parameters before approving creation."
        ),
        campaigns=[feed_campaign],
    )
