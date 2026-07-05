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
