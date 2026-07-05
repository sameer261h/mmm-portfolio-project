"""Append-only local audit log for proposed and approved campaign actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_LOG_PATH = Path("ads_agent/audit_log.jsonl")


def write_audit_event(event_type: str, payload: dict[str, Any]) -> None:
    """Write one JSON line so Sameer can prove every action had an audit trail."""

    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, default=str) + "\n")


def read_audit_events(event_type: str | None = None) -> list[dict[str, Any]]:
    """Read back logged events, optionally filtered by event_type.

    Used by the Phase 3 rate-limit guardrail to count today's applied writes --
    the audit log doubles as the source of truth for "how many changes have
    already happened today" instead of tracking a separate counter.
    """

    if not AUDIT_LOG_PATH.exists():
        return []

    events = []
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event_type is None or event["event_type"] == event_type:
                events.append(event)
    return events
