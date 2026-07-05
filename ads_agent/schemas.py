"""Structured data models for agent-generated Google Ads campaign plans."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CampaignType(str, Enum):
    SEARCH = "SEARCH"
    PERFORMANCE_MAX = "PERFORMANCE_MAX"


class CampaignStatus(str, Enum):
    PAUSED = "PAUSED"
    ENABLED = "ENABLED"


class Keyword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=2, max_length=80)
    match_type: Literal["EXACT", "PHRASE", "BROAD"] = "PHRASE"
    rationale: str = Field(min_length=10, max_length=300)


class SearchAdDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headlines: list[str] = Field(min_length=3, max_length=15)
    descriptions: list[str] = Field(min_length=2, max_length=4)


class PMaxAssetDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headlines: list[str] = Field(min_length=3, max_length=15)
    long_headlines: list[str] = Field(min_length=1, max_length=5)
    descriptions: list[str] = Field(min_length=2, max_length=5)
    audience_signals: list[str] = Field(default_factory=list, max_length=10)


class CampaignDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_type: CampaignType
    name: str = Field(min_length=3, max_length=128)
    daily_budget: float = Field(gt=0)
    status: CampaignStatus = CampaignStatus.PAUSED
    bid_strategy: str = Field(min_length=3, max_length=80)
    landing_page_url: str = Field(min_length=8, pattern=r"^https?://")
    geo_targets: list[str] = Field(default_factory=lambda: ["United States"])
    languages: list[str] = Field(default_factory=lambda: ["English"])
    rationale: str = Field(min_length=20, max_length=1200)
    editable_parameters: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    keywords: list[Keyword] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    search_ad: SearchAdDraft | None = None
    pmax_assets: PMaxAssetDraft | None = None

    @model_validator(mode="after")
    def validate_type_specific_assets(self) -> "CampaignDraft":
        if self.campaign_type == CampaignType.SEARCH:
            if not self.keywords:
                raise ValueError("Search campaigns require keywords.")
            if self.search_ad is None:
                raise ValueError("Search campaigns require a responsive search ad draft.")
        if self.campaign_type == CampaignType.PERFORMANCE_MAX and self.pmax_assets is None:
            raise ValueError("Performance Max campaigns require asset drafts.")
        return self


class CampaignPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=2, max_length=120)
    total_daily_budget: float = Field(gt=0)
    landing_page_url: str = Field(min_length=8, pattern=r"^https?://")
    mmm_summary: str = Field(min_length=20, max_length=1500)
    executive_summary: str = Field(min_length=20, max_length=1500)
    campaigns: list[CampaignDraft] = Field(min_length=2)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("campaigns")
    @classmethod
    def require_search_and_pmax(cls, campaigns: list[CampaignDraft]) -> list[CampaignDraft]:
        campaign_types = {campaign.campaign_type for campaign in campaigns}
        if CampaignType.SEARCH not in campaign_types:
            raise ValueError("Plan must include one Search campaign.")
        if CampaignType.PERFORMANCE_MAX not in campaign_types:
            raise ValueError("Plan must include one Performance Max campaign.")
        return campaigns


class ChangeAction(str, Enum):
    UPDATE_BUDGET = "UPDATE_BUDGET"
    PAUSE_CAMPAIGN = "PAUSE_CAMPAIGN"
    ADD_NEGATIVE_KEYWORD = "ADD_NEGATIVE_KEYWORD"


class ChangeTicket(BaseModel):
    """A Phase 3 write proposal: what the agent wants to do and why.

    The operator agent can only ever *create* one of these -- applying it is a
    separate function the Streamlit approval button calls, so there is no code
    path where the LLM's output directly mutates anything.
    """

    model_config = ConfigDict(extra="forbid")

    action: ChangeAction
    campaign_id: str = Field(min_length=1)
    campaign_name: str = Field(min_length=1)
    current_value: str = Field(min_length=1, max_length=200)
    proposed_value: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=10, max_length=500)
    expected_impact: str = Field(min_length=10, max_length=500)
