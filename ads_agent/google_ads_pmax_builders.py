"""Real Google Ads API mutate builders for Performance Max campaigns.

CONFIRMED WORKING (2026-07-05): verified live -- a real PAUSED Performance Max
campaign with a fully-linked asset group (10 assets) was created and
independently confirmed by querying the account afterward. Getting here took
several rounds of real, live-only errors (Brand Guidelines requiring a
business name + logo, an atomic per-operation asset-count validation that
requires the exact submission order used below, a missing business-name
asset entirely) -- see HANDOFF.md's status log for the full list. This was
the highest-risk, least-predictable part of the whole project; the compound
`GoogleAdsService.mutate()` pattern with temporary resource names and strict
operation ordering (campaign -> assets -> asset group -> links) is what
actually made it work, not the simpler sequential approach tried first.

Also generates placeholder marketing images with PIL, since PMax asset
groups require real image assets (logo, square marketing image, landscape
marketing image) and this project has none. These are obvious solid-color
placeholders with a text label, not real ad creative.
"""

from __future__ import annotations

import io

from ads_agent.google_ads_builders import _add_language_criteria, _create_budget, unique_campaign_name
from ads_agent.schemas import CampaignDraft

_HEADLINE_MAX_CHARS = 30
_LONG_HEADLINE_MAX_CHARS = 90
_DESCRIPTION_MAX_CHARS = 90

# (label, width, height, RGB color) -- dimensions match Google's recommended
# (not just minimum) asset sizes so the placeholders aren't rejected for
# being too small.
_IMAGE_SPECS = [
    ("logo", 1200, 1200, (66, 133, 244)),
    ("square_marketing_image", 1200, 1200, (52, 168, 83)),
    ("marketing_image", 1200, 628, (234, 67, 53)),
]


def _generate_placeholder_image(width: int, height: int, label: str, color: tuple[int, int, int]) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(image)
    draw.multiline_text((20, 20), f"PLACEHOLDER\n{label}\n{width}x{height}", fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def create_pmax_campaign(
    client, customer_id: str, campaign_draft: CampaignDraft, business_name: str = "Advertiser"
) -> dict[str, object]:
    """Create a real, paused Performance Max campaign.

    Google validates a Performance Max asset group's minimum asset counts
    (headlines, descriptions, business name, images, ...) *atomically at
    creation time*, checked against whatever the batch has already
    established *by that point in submission order* -- found via real
    testing, 2026-07-05, in two stages:
    1. Creating an empty AssetGroup first and linking assets in a separate,
       later call always fails (the assets don't exist yet at all when the
       AssetGroup is validated) -- fixed by submitting everything as one
       compound `GoogleAdsService.mutate()` batch with temporary
       negative-numbered resource names.
    2. Even within one compound batch, the AssetGroupOperation still failed
       when placed *before* its assets in the operations list -- Google
       appears to validate each operation against what preceded it in the
       list, not the batch as a whole. Fixed by ordering strictly as:
       campaign -> all assets (including a business name text asset, which
       turned out to be a baseline PMax requirement regardless of the
       account's Brand Guidelines setting) -> asset group -> asset-group
       links, last.
    """

    if campaign_draft.pmax_assets is None:
        raise ValueError("Performance Max campaign draft is missing its pmax_assets.")

    budget_resource_name = _create_budget(client, customer_id, campaign_draft)

    ga_service = client.get_service("GoogleAdsService")
    mutate_operations: list = []
    temp_id_state = {"next": -1}

    def temp_resource_name(resource: str) -> str:
        temp_id = temp_id_state["next"]
        temp_id_state["next"] -= 1
        return f"customers/{customer_id}/{resource}/{temp_id}"

    # 1. Campaign
    campaign_resource_name = temp_resource_name("campaigns")
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.create
    campaign.resource_name = campaign_resource_name
    campaign.name = unique_campaign_name(campaign_draft.name)
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.campaign_budget = budget_resource_name
    # Activates the maximize_conversions bidding-strategy oneof. This message
    # has no required fields, so writing target_cpa_micros=0 (meaning "no
    # target, let Google optimize") is what forces proto-plus to select this
    # branch of the oneof, matching Search's manual_cpc pattern -- confirmed
    # working via real testing, 2026-07-05.
    campaign.maximize_conversions.target_cpa_micros = 0
    # (No url_expansion_opt_out field exists on Campaign in this API version --
    # checked directly against the installed client's protobuf descriptor.
    # Leaving Google's default final-URL-expansion behavior in place.)
    # Required field as of this API version -- confirmed via real live testing
    # of the Search builder (2026-07-05); Campaign-level, so applies here too.
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )
    # This account has "Brand Guidelines" enabled, which otherwise requires a
    # business name + logo linked as CampaignAssets before the campaign can be
    # created at all. Simpler to opt this campaign out of it entirely.
    campaign.brand_guidelines_enabled = False
    campaign_mutate_op = client.get_type("MutateOperation")
    campaign_mutate_op.campaign_operation = campaign_operation
    campaign_op_index = len(mutate_operations)
    mutate_operations.append(campaign_mutate_op)

    # 2. All assets, collecting (resource_name, field_type) pairs to link once
    # the asset group exists -- must come before the AssetGroupOperation.
    asset_links: list[tuple[str, object]] = []

    def add_asset(build_asset, field_type) -> None:
        asset_resource_name = temp_resource_name("assets")
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.resource_name = asset_resource_name
        build_asset(asset)
        asset_mutate_op = client.get_type("MutateOperation")
        asset_mutate_op.asset_operation = asset_operation
        mutate_operations.append(asset_mutate_op)
        asset_links.append((asset_resource_name, field_type))

    for headline in campaign_draft.pmax_assets.headlines:
        add_asset(
            lambda asset, text=headline[:_HEADLINE_MAX_CHARS]: setattr(asset.text_asset, "text", text),
            client.enums.AssetFieldTypeEnum.HEADLINE,
        )
    for long_headline in campaign_draft.pmax_assets.long_headlines:
        add_asset(
            lambda asset, text=long_headline[:_LONG_HEADLINE_MAX_CHARS]: setattr(asset.text_asset, "text", text),
            client.enums.AssetFieldTypeEnum.LONG_HEADLINE,
        )
    for description in campaign_draft.pmax_assets.descriptions:
        add_asset(
            lambda asset, text=description[:_DESCRIPTION_MAX_CHARS]: setattr(asset.text_asset, "text", text),
            client.enums.AssetFieldTypeEnum.DESCRIPTION,
        )
    add_asset(
        lambda asset, text=business_name[:_HEADLINE_MAX_CHARS]: setattr(asset.text_asset, "text", text),
        client.enums.AssetFieldTypeEnum.BUSINESS_NAME,
    )

    image_field_types = {
        "logo": client.enums.AssetFieldTypeEnum.LOGO,
        "square_marketing_image": client.enums.AssetFieldTypeEnum.SQUARE_MARKETING_IMAGE,
        "marketing_image": client.enums.AssetFieldTypeEnum.MARKETING_IMAGE,
    }
    for label, width, height, color in _IMAGE_SPECS:
        image_bytes = _generate_placeholder_image(width, height, label, color)

        def build_image_asset(asset, data=image_bytes, name=f"{campaign_draft.name} {label} (placeholder)") -> None:
            asset.name = name
            asset.image_asset.data = data

        add_asset(build_image_asset, image_field_types[label])

    # 3. Asset group -- after all its assets already exist in the batch.
    asset_group_resource_name = temp_resource_name("assetGroups")
    asset_group_operation = client.get_type("AssetGroupOperation")
    asset_group = asset_group_operation.create
    asset_group.resource_name = asset_group_resource_name
    asset_group.name = f"{campaign_draft.name} Asset Group"
    asset_group.campaign = campaign_resource_name
    asset_group.final_urls.append(campaign_draft.landing_page_url)
    asset_group.status = client.enums.AssetGroupStatusEnum.PAUSED
    asset_group_mutate_op = client.get_type("MutateOperation")
    asset_group_mutate_op.asset_group_operation = asset_group_operation
    asset_group_op_index = len(mutate_operations)
    mutate_operations.append(asset_group_mutate_op)

    # 4. Links, last of all.
    for asset_resource_name, field_type in asset_links:
        link_operation = client.get_type("AssetGroupAssetOperation")
        link = link_operation.create
        link.asset_group = asset_group_resource_name
        link.asset = asset_resource_name
        link.field_type = field_type
        link_mutate_op = client.get_type("MutateOperation")
        link_mutate_op.asset_group_asset_operation = link_operation
        mutate_operations.append(link_mutate_op)

    response = ga_service.mutate(customer_id=customer_id, mutate_operations=mutate_operations)

    real_campaign_resource_name = response.mutate_operation_responses[campaign_op_index].campaign_result.resource_name
    real_asset_group_resource_name = response.mutate_operation_responses[
        asset_group_op_index
    ].asset_group_result.resource_name

    _add_language_criteria(client, customer_id, real_campaign_resource_name, campaign_draft.languages)

    return {
        "action": "CREATE_PAUSED_CAMPAIGN",
        "campaign_type": "PERFORMANCE_MAX",
        "name": campaign_draft.name,
        "campaign_resource_name": real_campaign_resource_name,
        "asset_group_resource_name": real_asset_group_resource_name,
        "daily_budget": campaign_draft.daily_budget,
        "status": "PAUSED",
        "placeholder_images_generated": [spec[0] for spec in _IMAGE_SPECS],
    }
