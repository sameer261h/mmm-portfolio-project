"""Structured data models for agent-generated Meta (Facebook/Instagram) Ads campaign plans.

Mirrors ads_agent/schemas.py's CampaignPlan/CampaignDraft shape, but for
Meta's Campaign -> Ad Set -> Ad structure instead of Google's Campaign ->
Ad Group -> Ad. Kept as a fully separate set of models (not an extension of
CampaignPlan) so the existing, already-verified-live Google Ads schemas and
their validators are never touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ads_agent.schemas import CampaignStatus


class MetaCampaignObjective(str, Enum):
    OUTCOME_TRAFFIC = "OUTCOME_TRAFFIC"
    OUTCOME_SALES = "OUTCOME_SALES"
    OUTCOME_LEADS = "OUTCOME_LEADS"
    OUTCOME_AWARENESS = "OUTCOME_AWARENESS"


class MetaAdCreativeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_texts: list[str] = Field(min_length=1, max_length=5)
    headlines: list[str] = Field(min_length=1, max_length=5)
    descriptions: list[str] = Field(default_factory=list, max_length=5)
    call_to_action: Literal["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "GET_QUOTE", "CONTACT_US"] = "LEARN_MORE"


class MetaCampaignDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=128)
    objective: MetaCampaignObjective
    daily_budget: float = Field(gt=0)
    status: CampaignStatus = CampaignStatus.PAUSED
    landing_page_url: str = Field(min_length=8, pattern=r"^https?://")
    geo_targets: list[str] = Field(default_factory=lambda: ["United States"])
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: list[Literal["male", "female", "all"]] = Field(default_factory=lambda: ["all"])
    interests: list[str] = Field(default_factory=list, max_length=10)
    rationale: str = Field(min_length=20, max_length=1200)
    editable_parameters: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    creative: MetaAdCreativeDraft


class MetaCampaignPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=2, max_length=120)
    total_daily_budget: float = Field(gt=0)
    landing_page_url: str = Field(min_length=8, pattern=r"^https?://")
    mmm_summary: str = Field(min_length=20, max_length=1500)
    executive_summary: str = Field(min_length=20, max_length=1500)
    campaigns: list[MetaCampaignDraft] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
