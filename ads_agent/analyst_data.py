"""Deterministic mock Google Ads performance data.

Phase 2 tools are read-only, but Basic API access is still pending Google's
review (see GOOGLE_ADS_AGENT_PLAN.md Phase 0), so there is no live Ads account
to query yet. This module stands in for real Google Ads API responses so the
analyst agent can be built and demoed now. The seeded random generator means
every run produces the exact same numbers -- useful for tests and for a
repeatable interview demo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    campaign_type: str
    status: str
    daily_budget: float


MOCK_CAMPAIGNS: list[Campaign] = [
    Campaign(
        id="1000000001",
        name="MMM-Agent-Demo-Search",
        campaign_type="SEARCH",
        status="ENABLED",
        daily_budget=56.39,
    ),
    Campaign(
        id="1000000002",
        name="MMM-Agent-Demo-PMax",
        campaign_type="PERFORMANCE_MAX",
        status="ENABLED",
        daily_budget=43.61,
    ),
]


@dataclass(frozen=True)
class DailyPerformance:
    campaign_id: str
    date: date
    impressions: int
    clicks: int
    cost: float
    conversions: float

    @property
    def cpa(self) -> float | None:
        if self.conversions == 0:
            return None
        return round(self.cost / self.conversions, 2)

    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0
        return round(self.clicks / self.impressions, 4)


def generate_daily_performance(days: int = 14) -> list[DailyPerformance]:
    """Seeded daily performance rows for every mock campaign.

    Search is modeled with a rising cost-per-click and a softening conversion
    rate across the window, so its CPA visibly climbs -- that's the scenario
    behind the "why did CPA rise last week?" question Phase 2 is meant to
    answer. PMax stays roughly flat as a contrast.
    """

    rows: list[DailyPerformance] = []
    today = date.today()

    for campaign in MOCK_CAMPAIGNS:
        # Seed per (campaign, day) so results never change between runs.
        rng = random.Random(f"{campaign.id}")
        for day_offset in range(days):
            day = today - timedelta(days=days - day_offset - 1)
            impressions = rng.randint(800, 1500)
            clicks = rng.randint(40, 120)
            conversions = round(rng.uniform(1.0, 6.0), 1)

            # Peg daily cost to the campaign's own budget (+/- normal pacing
            # noise) so spend/budget pacing looks like a real account instead
            # of drifting to an unrelated multiple of it.
            if campaign.campaign_type == "SEARCH":
                cost = round(campaign.daily_budget * rng.uniform(0.85, 1.05), 2)
                conversions = max(round(conversions * (1 - (day_offset / days) * 0.3), 1), 0.1)
            else:
                cost = round(campaign.daily_budget * rng.uniform(0.80, 1.00), 2)

            rows.append(
                DailyPerformance(
                    campaign_id=campaign.id,
                    date=day,
                    impressions=impressions,
                    clicks=clicks,
                    cost=cost,
                    conversions=conversions,
                )
            )

    return rows


@dataclass(frozen=True)
class SearchTerm:
    campaign_id: str
    term: str
    clicks: int
    cost: float
    conversions: float


MOCK_SEARCH_TERMS: list[SearchTerm] = [
    SearchTerm(campaign_id="1000000001", term="buy retail products", clicks=142, cost=210.33, conversions=9.0),
    SearchTerm(campaign_id="1000000001", term="retail products deals", clicks=98, cost=165.40, conversions=6.0),
    SearchTerm(campaign_id="1000000001", term="best retail products", clicks=64, cost=120.10, conversions=1.0),
    SearchTerm(campaign_id="1000000001", term="free retail products", clicks=51, cost=88.75, conversions=0.0),
    SearchTerm(campaign_id="1000000001", term="anonymized retailer jobs", clicks=12, cost=14.20, conversions=0.0),
]
