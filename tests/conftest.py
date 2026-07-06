from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _clean_ads_state():
    """Reset the on-disk audit log, operator-state overlay, and simulated-day
    clock around each test.

    Phase 3 writes and Phase 5's simulated clock actually persist to these
    files, so without this, tests that apply changes (or advance simulated
    days, or hit the daily rate limit) would pollute each other's state
    across runs.
    """

    from ads_agent.audit import AUDIT_LOG_PATH
    from ads_agent.operator_state import STATE_PATH
    from ads_agent.simulation_state import STATE_PATH as SIM_STATE_PATH

    AUDIT_LOG_PATH.unlink(missing_ok=True)
    STATE_PATH.unlink(missing_ok=True)
    SIM_STATE_PATH.unlink(missing_ok=True)
    yield
    AUDIT_LOG_PATH.unlink(missing_ok=True)
    STATE_PATH.unlink(missing_ok=True)
    SIM_STATE_PATH.unlink(missing_ok=True)
