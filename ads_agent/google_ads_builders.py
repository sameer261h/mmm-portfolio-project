"""Real Google Ads API mutate builders for Phase 4 campaign creation.

CONFIRMED WORKING (2026-07-05): verified live against a real Google Ads test
account, then double-checked by querying the account back afterward (not
just trusting the API's "success" response) -- see HANDOFF.md's status log
for the full list of real bugs this surfaced and how each was fixed
(FieldMask import, manual_cpc oneof activation, required
contains_eu_political_advertising field, CampaignBudget.explicitly_shared,
campaign name uniqueness).

Known simplifications, called out here rather than silently guessed at:
- Geo targeting (campaign_draft.geo_targets) is NOT applied as real location
  criteria -- that needs a GeoTargetConstantService name-to-ID lookup this
  first pass doesn't do. Campaigns are created with no location restriction.
- Language targeting uses a small hardcoded map of Google's well-known
  language constant IDs (these are stable, documented values, not something
  that needs an API lookup) and silently skips languages not in the map.
- RSA headlines/descriptions are truncated to Google's character limits (30 /
  90 chars) since ads_agent/schemas.py only constrains item *count*, not
  length -- an LLM-written headline could otherwise exceed what the real API
  accepts.
"""

from __future__ import annotations

from datetime import datetime

from ads_agent.schemas import CampaignDraft, CampaignType


def unique_campaign_name(base_name: str) -> str:
    """Append a timestamp so campaign names never collide.

    Google Ads requires campaign names to be unique among active/paused
    campaigns per account. The LLM-drafted name has no such guarantee (found
    via real testing, 2026-07-05: DUPLICATE_CAMPAIGN_NAME on a second run
    with the same inputs) -- this makes uniqueness the builder's job, not the
    planner's.
    """

    return f"{base_name} {datetime.now().strftime('%Y%m%d-%H%M%S')}"

# Google's well-known, stable language constant resource names -- see
# https://developers.google.com/google-ads/api/reference/data/codes-formats#languages
_LANGUAGE_CONSTANTS = {
    "english": "languageConstants/1000",
    "spanish": "languageConstants/1003",
    "french": "languageConstants/1002",
    "german": "languageConstants/1001",
}

_HEADLINE_MAX_CHARS = 30
_DESCRIPTION_MAX_CHARS = 90
_LONG_HEADLINE_MAX_CHARS = 90


def create_campaign_from_draft(
    client, customer_id: str, campaign_draft: CampaignDraft, business_name: str = "Advertiser"
) -> dict[str, object]:
    """Create one real (paused) campaign from an LLM-drafted CampaignDraft."""

    if campaign_draft.campaign_type == CampaignType.SEARCH:
        return _create_search_campaign(client, customer_id, campaign_draft)

    from ads_agent.google_ads_pmax_builders import create_pmax_campaign

    return create_pmax_campaign(client, customer_id, campaign_draft, business_name=business_name)


def _create_budget(client, customer_id: str, campaign_draft: CampaignDraft) -> str:
    budget_service = client.get_service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = operation.create
    budget.name = f"Budget for {campaign_draft.name}"
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.amount_micros = int(round(campaign_draft.daily_budget * 1_000_000))
    # Without this, new budgets default to shareable, which the API rejects
    # for per-campaign bidding strategies like manual_cpc/maximize_conversions
    # (found via real testing, 2026-07-05:
    # BIDDING_STRATEGY_TYPE_INCOMPATIBLE_WITH_SHARED_BUDGET). Each campaign
    # here gets its own budget, never shared.
    budget.explicitly_shared = False

    response = budget_service.mutate_campaign_budgets(
        customer_id=customer_id, operations=[operation]
    )
    return response.results[0].resource_name


def _add_language_criteria(client, customer_id: str, campaign_resource_name: str, languages: list[str]) -> None:
    criterion_service = client.get_service("CampaignCriterionService")
    operations = []
    for language in languages:
        resource_name = _LANGUAGE_CONSTANTS.get(language.strip().lower())
        if resource_name is None:
            continue
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = campaign_resource_name
        criterion.language.language_constant = resource_name
        operations.append(operation)

    if operations:
        criterion_service.mutate_campaign_criteria(customer_id=customer_id, operations=operations)


def _create_search_campaign(client, customer_id: str, campaign_draft: CampaignDraft) -> dict[str, object]:
    if campaign_draft.search_ad is None:
        raise ValueError("Search campaign draft is missing its search_ad.")

    budget_resource_name = _create_budget(client, customer_id, campaign_draft)

    campaign_service = client.get_service("CampaignService")
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.create
    campaign.name = unique_campaign_name(campaign_draft.name)
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    # Activates the manual_cpc bidding-strategy oneof via an empty submessage
    # assignment. `enhanced_cpc_enabled` looked like the natural field to set
    # here, but the live API rejected it with OPERATION_NOT_PERMITTED_FOR_CONTEXT
    # (found via real testing, 2026-07-05) -- Enhanced CPC appears restricted
    # for new campaigns in this API version. Assigning an empty ManualCpc
    # message activates the oneof without touching that field.
    campaign.manual_cpc = client.get_type("ManualCpc")
    campaign.campaign_budget = budget_resource_name
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True
    campaign.network_settings.target_content_network = False
    campaign.network_settings.target_partner_search_network = False
    # Required field as of this API version -- discovered via real testing
    # (2026-07-05), matches the same disclosure question Google's own UI
    # wizard asks ("Does your campaign have EU political ads?").
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )

    campaign_response = campaign_service.mutate_campaigns(
        customer_id=customer_id, operations=[campaign_operation]
    )
    campaign_resource_name = campaign_response.results[0].resource_name

    _add_language_criteria(client, customer_id, campaign_resource_name, campaign_draft.languages)

    ad_group_service = client.get_service("AdGroupService")
    ad_group_operation = client.get_type("AdGroupOperation")
    ad_group = ad_group_operation.create
    ad_group.name = f"{campaign_draft.name} Ad Group"
    ad_group.campaign = campaign_resource_name
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    ad_group_response = ad_group_service.mutate_ad_groups(
        customer_id=customer_id, operations=[ad_group_operation]
    )
    ad_group_resource_name = ad_group_response.results[0].resource_name

    match_type_map = {
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
    }
    criterion_service = client.get_service("AdGroupCriterionService")
    keyword_operations = []
    for keyword in campaign_draft.keywords:
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = ad_group_resource_name
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = keyword.text
        criterion.keyword.match_type = match_type_map[keyword.match_type]
        keyword_operations.append(operation)
    for negative_text in campaign_draft.negative_keywords:
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = ad_group_resource_name
        criterion.negative = True
        criterion.keyword.text = negative_text
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
        keyword_operations.append(operation)

    if keyword_operations:
        criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=keyword_operations
        )

    ad_group_ad_service = client.get_service("AdGroupAdService")
    ad_group_ad_operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = ad_group_ad_operation.create
    ad_group_ad.ad_group = ad_group_resource_name
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

    ad = ad_group_ad.ad
    ad.final_urls.append(campaign_draft.landing_page_url)
    for headline_text in campaign_draft.search_ad.headlines:
        headline_asset = client.get_type("AdTextAsset")
        headline_asset.text = headline_text[:_HEADLINE_MAX_CHARS]
        ad.responsive_search_ad.headlines.append(headline_asset)
    for description_text in campaign_draft.search_ad.descriptions:
        description_asset = client.get_type("AdTextAsset")
        description_asset.text = description_text[:_DESCRIPTION_MAX_CHARS]
        ad.responsive_search_ad.descriptions.append(description_asset)

    ad_group_ad_service.mutate_ad_group_ads(
        customer_id=customer_id, operations=[ad_group_ad_operation]
    )

    return {
        "action": "CREATE_PAUSED_CAMPAIGN",
        "campaign_type": "SEARCH",
        "name": campaign_draft.name,
        "campaign_resource_name": campaign_resource_name,
        "ad_group_resource_name": ad_group_resource_name,
        "daily_budget": campaign_draft.daily_budget,
        "status": "PAUSED",
        "keyword_count": len(campaign_draft.keywords),
    }
