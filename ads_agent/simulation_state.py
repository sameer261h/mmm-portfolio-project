"""Phase 5 simulated-day clock: no real ad spend, no real time, involved.

analyst_data.py's mock performance data used to be a static 14-day snapshot
pinned to real "today." This module adds a simulated day counter so that
clicking "Advance Day" in the Streamlit UI (or a scripted eval run) moves an
independent clock forward, and analyst_data.py's scenario script reveals a
worsening problem as that clock advances -- all synthetic, all offline.

Persisted to a JSON file (same pattern as ads_agent/operator_state.py) so the
count survives Streamlit's rerun-the-whole-script-every-interaction behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path("ads_agent/simulation_state.json")


def get_simulated_day() -> int:
    """How many synthetic days have been advanced. 0 = the original snapshot."""

    if not STATE_PATH.exists():
        return 0
    return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("day", 0)


def advance_simulated_day(days: int = 1) -> int:
    """Move the simulated clock forward and return the new day count."""

    new_day = get_simulated_day() + days
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"day": new_day}), encoding="utf-8")
    return new_day


def reset_simulation() -> None:
    """Back to day 0 -- used by the UI's Reset button and by test/eval cleanup."""

    STATE_PATH.unlink(missing_ok=True)
