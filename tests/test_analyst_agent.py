from __future__ import annotations

from ads_agent.analyst_agent import ask_analyst
from ads_agent.analyst_tools import (
    get_budget_pacing,
    get_performance,
    get_search_terms,
    list_campaigns,
)


def test_list_campaigns_returns_search_and_pmax() -> None:
    campaigns = list_campaigns()

    assert len(campaigns) == 2
    assert {c["campaign_type"] for c in campaigns} == {"SEARCH", "PERFORMANCE_MAX"}
    assert all(c["daily_budget"] > 0 for c in campaigns)


def test_get_performance_returns_one_row_per_campaign_per_day() -> None:
    rows = get_performance(date_range_days=7)

    assert len(rows) == 14  # 2 campaigns * 7 days
    assert all(row["impressions"] > 0 for row in rows)
    assert all(row["clicks"] >= 0 for row in rows)


def test_search_campaign_cpa_rises_over_the_window() -> None:
    # This is the exact scenario the analyst agent explains -- assert the
    # mock data actually produces a rising trend, not just plausible numbers.
    rows = get_performance(date_range_days=14)
    search_rows = [row for row in rows if row["campaign_id"] == "1000000001"]

    first_week_cpa = [row["cpa"] for row in search_rows[:7] if row["cpa"]]
    last_week_cpa = [row["cpa"] for row in search_rows[7:] if row["cpa"]]

    assert sum(last_week_cpa) / len(last_week_cpa) > sum(first_week_cpa) / len(first_week_cpa)


def test_get_search_terms_filters_by_campaign() -> None:
    all_terms = get_search_terms()
    filtered = get_search_terms(campaign_id="1000000001")
    missing_campaign = get_search_terms(campaign_id="does-not-exist")

    assert len(filtered) == len(all_terms)
    assert missing_campaign == []


def test_get_budget_pacing_covers_every_campaign() -> None:
    pacing = get_budget_pacing()

    assert len(pacing) == 2
    assert all(p["spend_so_far"] >= 0 for p in pacing)
    assert all(p["expected_spend_at_budget"] > 0 for p in pacing)


def test_ask_analyst_falls_back_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ask_analyst("Why did CPA rise last week?")

    assert result.tools_used == ["get_performance"]
    assert "CPA" in result.answer


def test_ask_analyst_routes_budget_questions(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ask_analyst("How is budget pacing looking this month?")

    assert result.tools_used == ["get_budget_pacing"]
    assert "paced" in result.answer


def test_ask_analyst_routes_search_term_questions(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ask_analyst("Which search terms are wasting spend?")

    assert result.tools_used == ["get_search_terms"]
    assert "CPA" in result.answer


def test_ask_analyst_falls_back_to_campaign_list_for_generic_questions(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ask_analyst("What campaigns exist?")

    assert result.tools_used == ["list_campaigns"]
    assert "MMM-Agent-Demo" in result.answer
