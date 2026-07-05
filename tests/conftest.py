from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _clean_ads_state():
    """Reset the on-disk audit log and operator-state overlay around each test.

    Phase 3 writes actually persist to these files, so without this, tests
    that apply changes (or hit the daily rate limit) would pollute each
    other's state across runs.
    """

    from ads_agent.audit import AUDIT_LOG_PATH
    from ads_agent.operator_state import STATE_PATH

    AUDIT_LOG_PATH.unlink(missing_ok=True)
    STATE_PATH.unlink(missing_ok=True)
    yield
    AUDIT_LOG_PATH.unlink(missing_ok=True)
    STATE_PATH.unlink(missing_ok=True)
