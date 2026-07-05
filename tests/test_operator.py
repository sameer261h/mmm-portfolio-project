from __future__ import annotations

import pytest

from ads_agent.analyst_tools import get_search_terms, list_campaigns
from ads_agent.google_ads_client import MockGoogleAdsClient
from ads_agent.guardrails import (
    GuardrailError,
    check_daily_write_rate_limit,
    validate_action_allowed,
    validate_budget_change,
)
from ads_agent.operator_agent import propose_change
from ads_agent.schemas import ChangeAction


def _search_campaign() -> dict[str, object]:
    return next(c for c in list_campaigns() if c["campaign_type"] == "SEARCH")


def _pmax_campaign() -> dict[str, object]:
    return next(c for c in list_campaigns() if c["campaign_type"] == "PERFORMANCE_MAX")


# --- guardrails -------------------------------------------------------------


def test_validate_budget_change_rejects_over_cap() -> None:
    with pytest.raises(GuardrailError):
        validate_budget_change(current_budget=50, new_budget=2000, max_daily_budget=1000)


def test_validate_budget_change_rejects_large_percentage_move() -> None:
    with pytest.raises(GuardrailError):
        validate_budget_change(current_budget=50, new_budget=150, max_daily_budget=1000)


def test_validate_budget_change_allows_small_move() -> None:
    validate_budget_change(current_budget=50, new_budget=60, max_daily_budget=1000)


def test_validate_action_allowed_rejects_unknown_action() -> None:
    with pytest.raises(GuardrailError):
        validate_action_allowed("DELETE_CAMPAIGN")


def test_check_daily_write_rate_limit_blocks_after_cap() -> None:
    client = MockGoogleAdsClient()
    search = _search_campaign()

    for _ in range(20):
        client.pause_campaign(campaign_id=search["id"], campaign_name=search["name"])

    with pytest.raises(GuardrailError):
        check_daily_write_rate_limit()


# --- MockGoogleAdsClient write methods ---------------------------------------


def test_update_campaign_budget_persists_and_shows_in_list_campaigns() -> None:
    client = MockGoogleAdsClient()
    search = _search_campaign()

    result = client.update_campaign_budget(
        campaign_id=search["id"],
        campaign_name=search["name"],
        current_daily_budget=search["daily_budget"],
        new_daily_budget=search["daily_budget"] * 1.1,
        max_daily_budget=1000,
    )

    assert result.mode == "mock"
    updated = next(c for c in list_campaigns() if c["id"] == search["id"])
    assert updated["daily_budget"] == round(search["daily_budget"] * 1.1, 2)


def test_pause_campaign_shows_in_list_campaigns() -> None:
    client = MockGoogleAdsClient()
    pmax = _pmax_campaign()

    client.pause_campaign(campaign_id=pmax["id"], campaign_name=pmax["name"])

    updated = next(c for c in list_campaigns() if c["id"] == pmax["id"])
    assert updated["status"] == "PAUSED"


def test_add_negative_keyword_removes_matching_search_terms() -> None:
    client = MockGoogleAdsClient()
    search = _search_campaign()

    before = [t["term"] for t in get_search_terms()]
    assert any("free" in term for term in before)

    client.add_negative_keyword(campaign_id=search["id"], campaign_name=search["name"], keyword_text="free")

    after = [t["term"] for t in get_search_terms()]
    assert not any("free" in term for term in after)


def test_add_negative_keyword_does_not_block_unrelated_terms() -> None:
    client = MockGoogleAdsClient()
    search = _search_campaign()

    client.add_negative_keyword(campaign_id=search["id"], campaign_name=search["name"], keyword_text="free")

    after = [t["term"] for t in get_search_terms()]
    assert "buy retail products" in after


# --- operator agent (deterministic fallback, no OpenAI key) ------------------


def test_propose_change_routes_pmax_pause_to_pmax_campaign(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ticket = propose_change("pause the pmax campaign")

    assert ticket.action == ChangeAction.PAUSE_CAMPAIGN
    assert ticket.campaign_name == "MMM-Agent-Demo-PMax"


def test_propose_change_routes_search_pause_to_search_campaign(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ticket = propose_change("pause the search campaign")

    assert ticket.action == ChangeAction.PAUSE_CAMPAIGN
    assert ticket.campaign_name == "MMM-Agent-Demo-Search"


def test_propose_change_routes_negative_keyword_request(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ticket = propose_change("some search terms are wasting spend, add a negative keyword")

    assert ticket.action == ChangeAction.ADD_NEGATIVE_KEYWORD
    assert ticket.proposed_value


def test_propose_change_defaults_to_budget_update(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ticket = propose_change("cut the search campaign budget, it is overspending")

    assert ticket.action == ChangeAction.UPDATE_BUDGET
    assert ticket.campaign_name == "MMM-Agent-Demo-Search"


def test_propose_change_never_applies_anything(monkeypatch) -> None:
    """The operator agent can only ever produce a ticket -- confirm nothing
    it does touches campaign state until a separate apply call happens."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    before = list_campaigns()

    propose_change("pause the search campaign")

    assert list_campaigns() == before
