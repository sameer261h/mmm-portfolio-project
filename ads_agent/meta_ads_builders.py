"""Real Meta (Facebook/Instagram) Marketing API mutate builders.

UNVERIFIED -- written against Meta's documented Marketing API, not yet
tested against a live account (Sameer has no Business Manager / App / Ad
Account set up yet as of 2026-07-05). Expect real bugs on first live run,
the same way Google Ads Phase 4 surfaced 7 real issues before being
confirmed -- treat every function here as best-effort correct until it's
actually been run once for real. See META_ADS_AGENT_PLAN.md for the setup
checklist and current status.

Known simplifications, called out here rather than silently guessed at:
- `interests` targeting (campaign_draft.interests) is NOT resolved to real
  Meta interest IDs -- that needs a Targeting Search API lookup this first
  pass doesn't do. Ad sets are created with only geo/age/gender targeting.
- Geo targeting uses a small hardcoded map of well-known country names to
  Meta's ISO country codes (same scoping decision as the Google builder's
  language-constant map), and silently falls back to "US" for anything not
  in the map.
- The ad creative requires a real, connected Facebook Page -- there is no
  way around this in Meta's model (a Feed ad is inherently posted "as" a
  Page). `META_ADS_PAGE_ID` must point to a real Page Sameer controls; this
  is a genuine setup requirement, not a shortcut we're taking.
- Uses a single placeholder image (from ads_agent/placeholder_images.py,
  shared with the Google PMax builder) as the ad creative's image asset,
  since this project has no real creative.
"""

from __future__ import annotations

import base64

from ads_agent.meta_schemas import MetaCampaignDraft, MetaCampaignObjective
from ads_agent.placeholder_images import generate_placeholder_image

_COUNTRY_CODES = {
    "united states": "US",
    "canada": "CA",
    "united kingdom": "GB",
    "australia": "AU",
}

_OPTIMIZATION_GOAL_BY_OBJECTIVE = {
    MetaCampaignObjective.OUTCOME_TRAFFIC: "LINK_CLICKS",
    MetaCampaignObjective.OUTCOME_SALES: "OFFSITE_CONVERSIONS",
    MetaCampaignObjective.OUTCOME_LEADS: "LEAD_GENERATION",
    MetaCampaignObjective.OUTCOME_AWARENESS: "REACH",
}

_GENDER_CODES = {"male": 1, "female": 2}


def _country_codes(geo_targets: list[str]) -> list[str]:
    codes = [_COUNTRY_CODES[g.strip().lower()] for g in geo_targets if g.strip().lower() in _COUNTRY_CODES]
    return codes or ["US"]


def _targeting_for(campaign_draft: MetaCampaignDraft) -> dict[str, object]:
    targeting: dict[str, object] = {
        "geo_locations": {"countries": _country_codes(campaign_draft.geo_targets)},
        "age_min": campaign_draft.age_min,
        "age_max": campaign_draft.age_max,
        # Now a required field ("Advantage audience flag required",
        # error_subcode 1870227). 0 = off, since this draft's age/geo targeting
        # is deliberate and shouldn't be silently widened by Meta's expansion.
        "targeting_automation": {"advantage_audience": 0},
    }
    if campaign_draft.genders != ["all"]:
        targeting["genders"] = [_GENDER_CODES[g] for g in campaign_draft.genders if g in _GENDER_CODES]
    return targeting


def create_meta_campaign_from_draft(
    ad_account_id: str, page_id: str, campaign_draft: MetaCampaignDraft
) -> dict[str, object]:
    """Create one real (paused) Meta campaign + ad set + creative + ad."""

    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adcreative import AdCreative
    from facebook_business.adobjects.adimage import AdImage
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.campaign import Campaign

    account = AdAccount(f"act_{ad_account_id}")

    # 1. Campaign. `special_ad_categories` is a required disclosure field --
    # plays the same role contains_eu_political_advertising did for Google
    # (empty list means "not a housing/credit/employment/political ad").
    campaign = account.create_campaign(
        params={
            Campaign.Field.name: campaign_draft.name,
            Campaign.Field.objective: campaign_draft.objective.value,
            Campaign.Field.status: Campaign.Status.paused,
            "special_ad_categories": [],
            # Budget lives on the ad set (not the campaign), so Meta requires
            # this to be explicit -- otherwise: "Must specify True or False in
            # is_adset_budget_sharing_enabled field" (error_subcode 4834011).
            "is_adset_budget_sharing_enabled": False,
        }
    )

    # 2. Ad set -- budget and targeting live here in Meta's model, not on
    # the campaign. daily_budget is in cents, mirroring Google's micros units.
    ad_set = account.create_ad_set(
        params={
            AdSet.Field.name: f"{campaign_draft.name} Ad Set",
            AdSet.Field.campaign_id: campaign["id"],
            AdSet.Field.daily_budget: int(round(campaign_draft.daily_budget * 100)),
            AdSet.Field.billing_event: AdSet.BillingEvent.impressions,
            AdSet.Field.optimization_goal: _OPTIMIZATION_GOAL_BY_OBJECTIVE[campaign_draft.objective],
            # Auto-bid, no manual cap -- avoids "Bid amount or bid constraints
            # required for bid strategy" (error_subcode 2490487), which fires
            # if bid_strategy is left unset.
            AdSet.Field.bid_strategy: AdSet.BidStrategy.lowest_cost_without_cap,
            AdSet.Field.targeting: _targeting_for(campaign_draft),
            AdSet.Field.status: AdSet.Status.paused,
        }
    )

    # 3. Creative -- needs a real image asset, uploaded as base64 bytes.
    image_bytes = generate_placeholder_image(1200, 628, campaign_draft.name, (66, 133, 244))
    image = account.create_ad_image(params={"bytes": base64.b64encode(image_bytes).decode("utf-8")})
    image_hash = image[AdImage.Field.hash]

    creative = account.create_ad_creative(
        params={
            AdCreative.Field.name: f"{campaign_draft.name} Creative",
            AdCreative.Field.object_story_spec: {
                "page_id": page_id,
                "link_data": {
                    "message": campaign_draft.creative.primary_texts[0],
                    "link": campaign_draft.landing_page_url,
                    "name": campaign_draft.creative.headlines[0],
                    "description": (campaign_draft.creative.descriptions or [""])[0],
                    "image_hash": image_hash,
                    "call_to_action": {"type": campaign_draft.creative.call_to_action},
                },
            },
        }
    )

    # 4. Ad, linking ad set + creative.
    ad = account.create_ad(
        params={
            Ad.Field.name: f"{campaign_draft.name} Ad",
            Ad.Field.adset_id: ad_set["id"],
            Ad.Field.creative: {"creative_id": creative["id"]},
            Ad.Field.status: Ad.Status.paused,
        }
    )

    return {
        "action": "CREATE_PAUSED_CAMPAIGN",
        "platform": "META",
        "objective": campaign_draft.objective.value,
        "name": campaign_draft.name,
        "campaign_id": campaign["id"],
        "ad_set_id": ad_set["id"],
        "ad_id": ad["id"],
        "daily_budget": campaign_draft.daily_budget,
        "status": "PAUSED",
    }
