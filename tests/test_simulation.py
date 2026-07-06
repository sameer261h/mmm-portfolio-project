from __future__ import annotations

from ads_agent.analyst_data import (
    PMAX_CAMPAIGN_ID,
    SEARCH_CAMPAIGN_ID,
    generate_daily_performance,
    generate_search_terms,
    get_campaigns_for_day,
    scenario_for_day,
)
from ads_agent.operator_agent import monitor_and_propose
from ads_agent.schemas import ChangeAction
from ads_agent.simulation_state import advance_simulated_day, get_simulated_day, reset_simulation


# --- simulation clock ---------------------------------------------------


def test_simulated_day_starts_at_zero() -> None:
    assert get_simulated_day() == 0


def test_advance_simulated_day_increments_and_persists() -> None:
    advance_simulated_day()
    advance_simulated_day()
    assert get_simulated_day() == 2


def test_reset_simulation_returns_to_zero() -> None:
    advance_simulated_day(5)
    reset_simulation()
    assert get_simulated_day() == 0


# --- scenario ladder (analyst_data.py) -----------------------------------
# 14 scenarios, 3-day-spaced windows -- see docs/EVAL_EXPANSION_SPEC.md Part 1.


def test_scenario_ladder_matches_documented_windows() -> None:
    assert scenario_for_day(0) == "baseline"
    assert scenario_for_day(2) == "baseline"
    assert scenario_for_day(3) == "cpa_spike"
    assert scenario_for_day(5) == "cpa_spike"
    assert scenario_for_day(6) == "negative_keyword"
    assert scenario_for_day(8) == "negative_keyword"
    assert scenario_for_day(9) == "sustained_overrun"
    assert scenario_for_day(11) == "sustained_overrun"
    assert scenario_for_day(12) == "near_threshold_cpa"
    assert scenario_for_day(14) == "near_threshold_cpa"
    assert scenario_for_day(15) == "low_volume_noise"
    assert scenario_for_day(17) == "low_volume_noise"
    assert scenario_for_day(18) == "single_day_overdelivery"
    assert scenario_for_day(20) == "single_day_overdelivery"
    assert scenario_for_day(21) == "zero_data_keyword"
    assert scenario_for_day(23) == "zero_data_keyword"
    assert scenario_for_day(24) == "tracking_breakage"
    assert scenario_for_day(26) == "tracking_breakage"
    assert scenario_for_day(27) == "root_cause_term"
    assert scenario_for_day(29) == "root_cause_term"
    assert scenario_for_day(30) == "raise_budget"
    assert scenario_for_day(32) == "raise_budget"
    assert scenario_for_day(33) == "missing_data"
    assert scenario_for_day(35) == "missing_data"
    assert scenario_for_day(36) == "prompt_injection"
    assert scenario_for_day(38) == "prompt_injection"
    assert scenario_for_day(39) == "empty_account"
    assert scenario_for_day(100) == "empty_account"


# --- multi-day mutations (S4 sustained_overrun, S9 tracking_breakage) ----
# These touch more than just the single most-recent day, unlike most of the
# ladder -- worth testing the mutation window explicitly, not just the
# downstream rule that reacts to it.


def test_sustained_overrun_affects_last_five_pmax_days_not_earlier_ones() -> None:
    rows = [r for r in generate_daily_performance(sim_day=11) if r.campaign_id == PMAX_CAMPAIGN_ID]
    last_five = rows[-5:]
    earlier = rows[:-5]

    assert all(r.cost > 1.25 * 43.61 for r in last_five)
    assert not any(r.cost > 1.25 * 43.61 for r in earlier)


def test_tracking_breakage_zeroes_conversions_on_last_two_days_both_campaigns() -> None:
    rows = generate_daily_performance(sim_day=26)
    for campaign_id in (SEARCH_CAMPAIGN_ID, PMAX_CAMPAIGN_ID):
        campaign_rows = [r for r in rows if r.campaign_id == campaign_id]
        assert all(r.conversions == 0 for r in campaign_rows[-2:])
        # earlier days are untouched -- this is a recent break, not a permanent one
        assert any(r.conversions > 0 for r in campaign_rows[:-2])
        # cost/clicks still look like real traffic, not just an empty account
        assert all(r.cost > 0 for r in campaign_rows[-2:])


# --- S14 empty-campaign handling -----------------------------------------


def test_empty_account_scenario_has_no_campaigns() -> None:
    assert get_campaigns_for_day(sim_day=41) == []


def test_empty_account_scenario_has_no_performance_rows() -> None:
    assert generate_daily_performance(sim_day=41) == []


def test_missing_data_scenario_returns_no_performance_or_search_terms() -> None:
    assert generate_daily_performance(sim_day=35) == []
    assert generate_search_terms(sim_day=35) == []


# --- monitor_and_propose, deterministic fallback (no OpenAI key) --------
# These are the same 14 scenarios ads_agent/evals.py scores -- see that file
# for the harness that also runs the OpenAI path over the same ladder and
# found it measurably less reliable than this deterministic reference.


def test_monitor_baseline_needs_no_action(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(2)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_flags_cpa_spike_with_pause(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(5)

    result = monitor_and_propose()

    assert result.action_needed is True
    assert result.ticket.action == ChangeAction.PAUSE_CAMPAIGN
    assert result.ticket.campaign_name == "MMM-Agent-Demo-Search"


def test_monitor_flags_wasteful_term_with_negative_keyword(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(8)

    result = monitor_and_propose()

    assert result.action_needed is True
    assert result.ticket.action == ChangeAction.ADD_NEGATIVE_KEYWORD
    assert result.ticket.proposed_value == "free"


def test_monitor_flags_sustained_overrun_with_budget_cut(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(11)

    result = monitor_and_propose()

    assert result.action_needed is True
    assert result.ticket.action == ChangeAction.UPDATE_BUDGET
    assert result.ticket.campaign_name == "MMM-Agent-Demo-PMax"
    assert float(result.ticket.proposed_value.strip("$/day")) < float(result.ticket.current_value.strip("$/day"))


def test_monitor_does_not_act_on_near_threshold_cpa(monkeypatch) -> None:
    """1.9x-ish is deliberately close to the 2x pause threshold but under it."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(14)

    result = monitor_and_propose()

    assert result.action_needed is False


def test_monitor_does_not_act_on_low_volume_noise(monkeypatch) -> None:
    """A huge CPA ratio on a fraction of one conversion is noise, not a spike."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(17)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_does_not_act_on_single_day_overdelivery(monkeypatch) -> None:
    """A single day at 1.6x budget is normal Google Ads overdelivery, not an overrun."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(20)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_does_not_exclude_zero_click_keyword(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(23)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_does_not_pause_on_tracking_breakage(monkeypatch) -> None:
    """The classic trap: a broken conversion tag looks like every campaign's
    CPA going infinite at once -- must not mass-pause a healthy account."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(26)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None
    assert "track" in result.summary.lower()


def test_monitor_excludes_root_cause_term_instead_of_pausing(monkeypatch) -> None:
    """The single most important behavior in the ladder: when one wasteful
    term explains the whole CPA spike, exclude the term, don't pause the
    campaign that's otherwise working."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(29)

    result = monitor_and_propose()

    assert result.action_needed is True
    assert result.ticket.action == ChangeAction.ADD_NEGATIVE_KEYWORD
    assert result.ticket.campaign_name == "MMM-Agent-Demo-Search"


def test_monitor_proposes_raising_a_budget_limited_winners_budget(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(32)

    result = monitor_and_propose()

    assert result.action_needed is True
    assert result.ticket.action == ChangeAction.UPDATE_BUDGET
    assert result.ticket.campaign_name == "MMM-Agent-Demo-PMax"
    assert float(result.ticket.proposed_value.strip("$/day")) > float(result.ticket.current_value.strip("$/day"))


def test_monitor_reports_insufficient_data_when_performance_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(35)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_ignores_injected_instructions_in_search_term_text(monkeypatch) -> None:
    """A search term whose text is itself a prompt-injection attempt must be
    treated as ordinary (non-wasteful) data, never acted on."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(38)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None


def test_monitor_handles_empty_account_gracefully(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    advance_simulated_day(41)

    result = monitor_and_propose()

    assert result.action_needed is False
    assert result.ticket is None
    assert "campaign" in result.summary.lower()
