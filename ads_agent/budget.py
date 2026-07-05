"""Translate MMM output into a Google-controllable budget envelope."""

from __future__ import annotations

from dataclasses import dataclass


# These numbers come from notebook 02's constrained optimizer output.
# Google Ads can directly execute Search, Display, and Video/PMax style activity.
MMM_RECOMMENDED_WEEKLY = {
    "search": 521_581.0,
    "display": 317_823.0,
    "digital_video": 85_517.0,
}

# Also from notebook 02's constrained optimizer output. `social` is the MMM's
# highest-percentage-growth recommendation of any channel (+75% vs. current
# $175,997/week) but was never wired into the agentic layer until the Meta
# Ads extension -- Google Ads has no way to spend against this channel.
MMM_RECOMMENDED_WEEKLY_META = {
    "social": 307_995.0,
}


@dataclass(frozen=True)
class BudgetSplit:
    """Daily budget split between the v1 Google Ads campaign types."""

    total_daily_budget: float
    search_daily_budget: float
    pmax_daily_budget: float
    search_share: float
    pmax_share: float


def calculate_google_ads_split(total_daily_budget: float) -> BudgetSplit:
    """Scale the MMM digital recommendation to any demo daily budget.

    Example:
    If Sameer enters $100/day, the app keeps the MMM proportions:
    roughly $56.40/day to Search and $43.60/day to PMax.
    """

    if total_daily_budget <= 0:
        raise ValueError("Total daily budget must be greater than 0.")

    search = MMM_RECOMMENDED_WEEKLY["search"]
    pmax = MMM_RECOMMENDED_WEEKLY["display"] + MMM_RECOMMENDED_WEEKLY["digital_video"]
    google_pool = search + pmax

    search_share = search / google_pool
    pmax_share = pmax / google_pool

    return BudgetSplit(
        total_daily_budget=round(total_daily_budget, 2),
        search_daily_budget=round(total_daily_budget * search_share, 2),
        pmax_daily_budget=round(total_daily_budget * pmax_share, 2),
        search_share=round(search_share, 4),
        pmax_share=round(pmax_share, 4),
    )


@dataclass(frozen=True)
class MetaBudgetSplit:
    """Daily budget for the v1 Meta Ads channel (a single Feed campaign type for now)."""

    total_daily_budget: float
    feed_daily_budget: float


def calculate_meta_ads_split(total_daily_budget: float) -> MetaBudgetSplit:
    """Scale a demo daily budget to the v1 Meta Ads envelope.

    Unlike Google Ads (which splits one pool across Search/PMax), v1 Meta
    support is a single Feed campaign, so there is nothing to split -- the
    whole entered budget goes to that one campaign.
    MMM_RECOMMENDED_WEEKLY_META["social"] is kept here so the plan's
    executive summary can cite the real MMM number that justifies why Meta
    gets budget in the first place.
    """

    if total_daily_budget <= 0:
        raise ValueError("Total daily budget must be greater than 0.")

    return MetaBudgetSplit(
        total_daily_budget=round(total_daily_budget, 2),
        feed_daily_budget=round(total_daily_budget, 2),
    )
