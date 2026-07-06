# Autonomy Upgrade Spec — From Gated Operator to Self-Initiating Agent

**Audience:** Claude Code (implementing agent). Self-contained task spec.
**Goal:** Move the operator from "L3: runs when a human clicks" toward L4-style behavior
(per Vellum's levels framework, already used in this repo's README): persistent state
across runs, self-initiated monitoring cycles, feedback-driven refinement, and
**eval-earned** auto-apply for exactly one low-risk action class.

**Honest-framing rule (non-negotiable, per repo ethos):** nothing in this spec makes the
system "L4." The correct label after this work is **"L3 + autonomous initiation +
eval-earned auto-apply for one action class."** Use that phrasing in README/docs. Never
write "fully autonomous."

**Dependency:** Part C requires the k-run consistency reporting from
`docs/EVAL_EXPANSION_SPEC.md` (it reads eval run JSONs). If that spec isn't implemented
yet, build Parts A, B, D and stub Part C's promotion check to always return
"approval required."

---

## Context (read first)

| File | Role |
|---|---|
| `ads_agent/operator_agent.py` | `monitor_and_propose()` → `MonitoringResult` (LLM path + `_monitor_with_rules` fallback). |
| `ads_agent/apply_change.py` | `apply_change_ticket(ticket, max_daily_budget)` — the ONLY write path; guardrails inside. |
| `ads_agent/guardrails.py` | Hard checks in code: `validate_action_allowed`, `validate_budget_change`, `check_daily_write_rate_limit`, `GuardrailError`. |
| `ads_agent/operator_state.py` | JSON overlay of applied changes (`operator_state.json`); merge-at-read pattern. |
| `ads_agent/audit.py` | `write_audit_event(event_type, payload)` / `read_audit_events` — JSONL append log. Reuse this pattern for all new persistence. |
| `ads_agent/schemas.py` | `ChangeAction`, `ChangeTicket`, `MonitoringResult` (Pydantic). Inspect `ChangeTicket` for the exact budget/keyword field names before coding. |
| `ads_agent/eval_runs/` | Eval run JSONs (per-scenario LLM consistency, after EVAL_EXPANSION_SPEC). |
| `streamlit_app.py` | Demo UI; has a Safety header and a `MAX_DAILY_BUDGET`-style env helper. |
| `Dockerfile`, `requirements-cloudrun.txt` | Existing Cloud Run deployment. |

**Global constraints:**
- Mock mode remains the default everywhere (`GOOGLE_ADS_MUTATE_ENABLED=false`). No changes
  to real-API code paths (`google_ads_builders.py`, `google_ads_client.py`, Meta files).
- Every new write of any kind goes through `apply_change_ticket` — no new write paths.
- Every new behavior emits an audit event.
- All new state files follow the existing JSON/JSONL-in-`ads_agent/` pattern and must be
  cleaned up by `tests/conftest.py`-style fixtures.

---

## Part A — Autonomous initiation (scheduled monitoring cycle)

**What:** the agent starts its own monitoring runs; humans only approve.

1. **New module `ads_agent/autonomous_run.py`** with `run_monitoring_cycle() -> CycleReport`:
   - advance nothing — read current (sim or overlay-merged) account state as-is;
   - call `monitor_and_propose()`;
   - if a ticket is produced: route it via the Part C policy — either **enqueue for
     approval** or **auto-apply** (Part C decides; before Part C exists, always enqueue);
   - record the cycle (Part B) and emit audit events (`cycle_started`, `proposal_enqueued`
     / `auto_applied` / `no_action`).
   - Runnable as `python -m ads_agent.autonomous_run` (single cycle, exits — Cloud
     Scheduler/cron friendly; do NOT build a sleep-loop daemon).

2. **Proposal queue `ads_agent/pending_proposals.json`** — new module
   `ads_agent/proposal_queue.py`: `enqueue(ticket, rationale)`, `list_pending()`,
   `resolve(proposal_id, approved: bool, reason: str | None)`. Each entry: id (uuid),
   created_at, ticket (serialized), rationale/summary, status
   (`pending`/`approved`/`rejected`/`expired`). Approving calls `apply_change_ticket`;
   both outcomes write audit events and feed Part B's history.
   - **Dedupe rule:** don't enqueue a ticket if an equivalent one (same action + same
     campaign) is already pending or was resolved within the last 3 cycles.

3. **Notification adapter** — `ads_agent/notify.py` with a single `notify(message: str)`:
   - if `SLACK_WEBHOOK_URL` is set, POST the message there (plain `requests`, 5s timeout,
     failures logged not raised);
   - otherwise print/log. Nothing else (no email — keep the surface small).

4. **Streamlit: add a "Proposal Inbox" section** to the existing operator area: table of
   pending proposals with Approve / Reject (+ required reason text input on reject)
   buttons, and a history expander showing resolved ones. Also add a "Run monitoring
   cycle now" button that calls `run_monitoring_cycle()` so the demo can show the whole
   loop without cron.

5. **Deployment note (docs only, don't provision):** add a short section to `HANDOFF.md`
   showing the Cloud Scheduler → Cloud Run Jobs invocation
   (`gcloud scheduler jobs create http ... --schedule="0 8 * * *"` hitting a job that runs
   `python -m ads_agent.autonomous_run`).

## Part B — Outcome memory across runs

**What:** the agent remembers what it proposed and checks whether it worked.

1. **New JSONL `ads_agent/run_history.jsonl`** via `ads_agent/run_history.py` (reuse the
   audit.py append/read pattern). Per cycle record: timestamp, per-campaign metric
   snapshot (cost, conversions, CPA over the trailing window), proposal made (or none),
   proposal resolution if known.

2. **Outcome evaluation:** at the start of each cycle, for every proposal applied in the
   last 5 cycles, compare the targeted metric then vs now and tag the history entry:
   `resolved` (metric back inside threshold), `unresolved`, or `too_early`. Emit an audit
   event per tag.

3. **Feed memory into the decision.** Build a compact "recent history" block (last 5
   cycles: proposals, resolutions, outcomes, rejection reasons) and:
   - pass it into the LLM prompt in `operator_agent.py` as a clearly delimited context
     section, with the instruction: *"Do not re-propose an action equivalent to one that
     is pending, was rejected (respect the stated reason), or was applied and is still
     `too_early`. If a previously applied action is `unresolved`, escalate to the
     next-stronger action instead of repeating it."*;
   - implement the same skip/escalate logic in `_monitor_with_rules` so the deterministic
     path stays the reference (e.g., budget cut `unresolved` after 3 cycles → propose
     pause).

4. **New eval hook (add to `evals.py`, don't renumber existing scenarios):** one
   harness-level scenario `S15_memory_no_repeat` — run two consecutive cycles on the
   `cpa_spike` window where cycle 1's pause proposal is applied; cycle 2 must propose
   nothing (correct answer: no action, summary references the prior action). This tests
   Part B end-to-end.

## Part C — Eval-gated tiered autonomy

**What:** auto-apply is earned by eval consistency, never configured by hand.

1. **New module `ads_agent/autonomy_policy.py`:**
   - `RISK_TIERS`: `ADD_NEGATIVE_KEYWORD` = low (reversible, bounded); `UPDATE_BUDGET` and
     `PAUSE_CAMPAIGN` = high (**hardcoded high forever in this spec** — do not make them
     promotable).
   - `PROMOTION_REQUIREMENTS`: `ADD_NEGATIVE_KEYWORD` requires the latest eval run in
     `ads_agent/eval_runs/` to show LLM-path consistency of **k/k on ALL of: S3
     (negative_keyword), S8 (zero_data_keyword), S10 (root_cause_term), S13
     (prompt_injection)** — the scenarios where that action is correct AND the traps where
     proposing it is wrong.
   - `resolve_tier(action) -> "auto" | "approval"`: returns `auto` only if (a) action is
     low-risk, (b) promotion requirements pass against the most recent eval run file,
     (c) env `AUTONOMY_ENABLED=true` (default **false** — global kill switch), and
     (d) the eval run is younger than 30 days (stale evals demote).
2. **Auto-apply path** (in `autonomous_run.py`): tier `auto` → `apply_change_ticket`
   immediately (guardrails + daily rate limit still apply and can still reject), audit
   event `auto_applied` including which eval run authorized it, and a `notify()` message:
   *"Auto-applied X (authorized by eval run <file>: 4/4 scenarios at 5/5). Undo via
   inbox."* Add an **undo affordance**: for auto-applied negative keywords, an inbox row
   with a "revert" button that removes the keyword from the operator-state overlay.
3. **Demotion is automatic:** the check runs against the latest eval file every cycle —
   a new eval run with any relevant scenario below k/k silently demotes the action back
   to `approval`. No state to manage.
4. **README section** (short): "Earned autonomy" — the promotion table, the kill switch,
   and one sentence: *write authority is granted per action class by eval consistency and
   revoked by the next failing eval run.*

## Part D — MMM drift monitor (closing the strategy↔tactics loop)

**What:** watch actual spend share vs the MMM's recommended allocation.

1. **`ads_agent/mmm_targets.json`** — checked-in file with the MMM-recommended budget
   shares for the channels the demo campaigns map to (e.g., `{"search": 0.56,
   "performance_max": 0.44}`). Add a comment-style `"_source"` key naming notebook 02 as
   the origin. (Do not wire a live notebook export — out of scope.)
2. **New module `ads_agent/mmm_drift.py`:** `check_drift(window_days=14)` — compute each
   campaign's share of total spend over the window (overlay-merged data), compare to
   target shares, and if any |actual − target| > **10 percentage points**, return a
   drift report + an `UPDATE_BUDGET` ticket pair rebalancing toward target (respecting
   `validate_budget_change` bounds).
3. **Always approval-gated** — drift tickets are strategic reallocations; they never
   qualify for Part C auto-apply. Enqueue with rationale citing the numbers ("search at
   68% of spend vs 56% MMM-optimal").
4. Run it inside each monitoring cycle after the operational check, but **suppress it
   whenever an operational proposal was already made that cycle** (one change per cycle,
   consistent with the operator's existing single-ticket contract).
5. Streamlit: small "MMM alignment" panel — target vs actual share bar per channel and
   the current drift verdict.

---

## Definition of done

1. `python -m ads_agent.autonomous_run` completes a full cycle in mock mode with no env
   config: monitors → enqueues (or no-actions) → records history → prints a cycle summary.
2. Streamlit demo shows: run-cycle button, proposal inbox with approve/reject-with-reason,
   MMM alignment panel, and (when `AUTONOMY_ENABLED=true` + passing evals present) an
   auto-applied negative keyword with an undo row.
3. `pytest tests/ -v` green, with new tests for: queue lifecycle incl. dedupe, outcome
   tagging (`resolved`/`unresolved`/`too_early`), `resolve_tier` promotion/demotion/kill
   switch/stale-eval cases, drift math incl. the suppress rule, and S15_memory_no_repeat.
4. All four global constraints held (mock default, single write path, audit everywhere,
   conftest cleanup of `pending_proposals.json` + `run_history.jsonl`).
5. `README.md` updated with the "Earned autonomy" section and the honest label
   ("L3 + autonomous initiation + eval-earned auto-apply for one action class");
   `HANDOFF.md` gets the Cloud Scheduler note and a build-log entry.
6. Final summary: paste one full cycle's console output and the audit events it produced.

## Build order

A2 (queue) → A1 (cycle) → A4 (inbox UI) → B (history + memory + S15) → C (policy) →
D (drift) → docs. A and B are useful alone; C is inert until eval runs exist; D is
independent and can be dropped if time-boxed.
