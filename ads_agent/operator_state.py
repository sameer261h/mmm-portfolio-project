"""Mutable overlay for demo campaign state, applied by Phase 3 operator writes.

ads_agent/analyst_data.py's MOCK_CAMPAIGNS never changes -- it's the
deterministic base data Phase 2 was built and tested against. Any
budget/status/negative-keyword change an operator approves in Phase 3 gets
recorded here instead, as a small JSON overlay keyed by campaign_id. Analyst
tools merge base + overlay at read time, so an approved change actually shows
up in later "ask the analyst" answers and campaign listings.

Backed by a JSON file (not just an in-memory dict) so changes survive across
Streamlit reruns -- Streamlit re-executes the whole script on every
interaction, which would otherwise wipe a plain module-level variable. Same
persistence pattern as ads_agent/audit_log.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_PATH = Path("ads_agent/operator_state.json")


def load_state() -> dict[str, dict[str, Any]]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, dict[str, Any]]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_campaign_overrides(campaign_id: str) -> dict[str, Any]:
    return load_state().get(campaign_id, {})


def apply_budget_override(campaign_id: str, new_daily_budget: float) -> None:
    state = load_state()
    state.setdefault(campaign_id, {})["daily_budget"] = new_daily_budget
    save_state(state)


def apply_pause_override(campaign_id: str) -> None:
    state = load_state()
    state.setdefault(campaign_id, {})["status"] = "PAUSED"
    save_state(state)


def apply_negative_keyword(campaign_id: str, keyword_text: str) -> None:
    state = load_state()
    entry = state.setdefault(campaign_id, {})
    negative_keywords = entry.setdefault("negative_keywords", [])
    if keyword_text not in negative_keywords:
        negative_keywords.append(keyword_text)
    save_state(state)
