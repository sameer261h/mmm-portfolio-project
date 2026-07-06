# Eval Scope Decisions — What's In, What's Out, and Why

Companion to `docs/EVAL_EXPANSION_SPEC.md` (the build instructions) and
`docs/EVAL_SCENARIOS.md` (the full 60-scenario catalog).

**The selection principle:** an eval scenario earns its place only if it tests a decision
the agent can currently make. The operator has exactly three write actions —
`UPDATE_BUDGET`, `PAUSE_CAMPAIGN`, `ADD_NEGATIVE_KEYWORD` — plus "do nothing."
Scenarios whose correct answer requires tools the agent doesn't have (ad copy edits, bid
adjustments, target-CPA changes, Meta actions) measure commentary, not agency. They're
deferred until the toolset grows, not discarded.

Second filter: **no new simulation modeling.** Everything included is data authoring
against existing fields (cost, budget, clicks, conversions, search terms, sim_day).
Anything needing new state (Quality Score, impression share, learning status, device/geo
segments, ad-set hierarchy) is out for this pass.

---

## Included — 14 scenarios

| # | Scenario | Catalog ID | Why it made the cut |
|---|----------|-----------|---------------------|
| S1 | `baseline` | G1 | Anchor. Every eval suite needs the "nothing is wrong" case or restraint is untestable. |
| S2 | `cpa_spike` | G2 | Existing core detection; kept as-is. |
| S3 | `negative_keyword` | G3 | Existing core detection; kept as-is. |
| S4 | `sustained_overrun` | G21 | Replaces the old budget_overrun, whose ground truth was **wrong** — Google legitimately overdelivers up to 2× daily budget in a day. Fixing an incorrect answer key outranks adding any new scenario. |
| S5 | `near_threshold_cpa` | G5 | Restraint trap. 1.8× vs a 2× threshold tests boundary discipline — the exact class where the LLM path currently flip-flops between runs. |
| S6 | `low_volume_noise` | G6 | Restraint trap. A "spike" on 0.3 conversions is noise; agents that can't tell significance from magnitude are dangerous with write access. |
| S7 | `single_day_overdelivery` | G8 | The trap twin of S4. Together they encode the overdelivery rule from both directions; either alone is half a lesson. |
| S8 | `zero_data_keyword` | G11 | Cheapest restraint case (data authoring only); catches trigger-happy keyword exclusion. |
| S9 | `tracking_breakage` | G16 | The classic account-killer: naive agents mass-pause a healthy account when the conversion tag breaks. Highest-severity failure mode reachable with existing fields. |
| S10 | `root_cause_term` | G34 | **The best scenario in the whole catalog.** Wasteful term IS the CPA spike — exclude (root cause) vs pause (symptom) is the cleanest separator between a reasoning agent and a checklist. Prime interview material. |
| S11 | `raise_budget` | G22 | The one genuine hole your pushback surfaced: without it, an agent with a systematic downward bias passes everything. `UPDATE_BUDGET` can go up — the action space isn't direction-covered without this. |
| S12 | `missing_data` | G37 | Hallucination check: empty API result must produce "insufficient data," not invented metrics. Trivial to build. |
| S13 | `prompt_injection` | G40 | Adversarial input via account content (search-term text). Near-zero build cost, high demo value, tests a property (data ≠ instructions) nothing else covers. |
| S14 | `empty_account` | G41 | Degenerate-input crash test. One conditional in the data layer. |

Coverage check: every action in the agent's vocabulary has ≥1 scenario where it's correct
(S2, S3/S10, S4, S11) and ≥1 where proposing it is a fail (S5/S6, S8, S7, S10) — plus
8 no-action scenarios feeding the restraint score.

---

## Dropped (deferred) — and the specific reason for each

| Catalog IDs | Group | Why dropped | What would unlock it |
|-------------|-------|-------------|---------------------|
| G7 | Attribution-lag restraint trap | Most real-world-common deferral, but modeling conversion lag *properly* is real time-series work; a hacked version teaches the agent a wrong lesson. Better absent than wrong. | Lag modeling in `generate_daily_performance` |
| G9, G33, G36 | Learning-period trap; multi-signal triage | Need a bid-strategy status field / multiple simultaneous live problems — the ladder currently scripts one problem per window. G9 is the cheapest future add (one status string). | Small `analyst_data` extensions; G9 first |
| G10, G12, G13 | Seasonality, brand context, gradual creep | Need richer history (weekly patterns, multi-week trends, assist metrics) than the 14-day single-mutation window provides. | Longer/patterned synthetic history |
| G14, G15 | Device/geo segment spikes | Correct answers (bid adjustments, geo exclusions) are **outside the action space**, and segment breakdowns don't exist in the data. Double-blocked. | Segment data + new actions |
| G17–G20 | Keyword variants (pattern negatives, brand misspelling, cannibalization) | Real but incremental — S3 + S8 + S10 already cover the keyword decision's core (exclude / don't exclude / exclude-instead-of-pause). These refine, not extend, coverage. | Nothing — add anytime; low priority |
| G22–G26 (except G22) | Tier 3 structural (underpacing, tCPA, PMax cannibalization, stale bids) | Correct answers need tools the agent doesn't have (target changes, strategy changes, brand exclusions). Testing recommendations the agent can't execute measures commentary. | Toolset expansion first |
| G27–G32 | Tier 4 Ad Rank / quality | Every scenario needs fields that don't exist (QS, IS lost-to-rank, disapproval status, ad strength) AND fixes outside the action space. Most expensive, least actionable — clearest drop. | QS/IS modeling + ad-level tools |
| G35 | Budget-limited + high CPA conflict | Worth having eventually, but its lesson (don't fund a fire) is partially embedded in S11's CPA condition. Needs the multi-signal window mechanic (same blocker as G33). | Multi-problem windows |
| G38, G39, G42 | Micros trap, duplicate names, partial-day window | G38/G42: the mock data layer doesn't have unit/timezone seams to corrupt — the scenario would test the simulator, not the agent. G39: blocked on the `campaign_name` → `entity_id` schema refactor (do that refactor when Meta work starts; it's a prerequisite there anyway). | Schema refactor (G39); richer data layer |
| M1–M18 | All Meta scenarios | Triple-blocked: Phase 6 has an external payment/region blocker, the ad-set/ad entity hierarchy doesn't exist in schemas, and none of the Meta action vocabulary is built. Building evals for a surface you can't write to is effort in the wrong order. | Phase 6 unblock → entity refactor → then M1, M3, M4, M6, M9, M12 first |

---

## The one-line summary

14 scenarios cover every decision category the agent can currently act on — detection in
both directions, restraint under four kinds of temptation, root-cause discrimination, and
data integrity — for a weekend of data authoring. The other 46 aren't lost; each row above
names exactly what has to exist before its scenario becomes a test of agency rather than
commentary.
