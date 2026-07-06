# Google Ads Agent — Build Plan

Companion project to the MMM. Goal: an agentic system that analyzes, proposes, and
(with your approval) executes Google Ads changes — eventually taking its budget
envelope from the MMM.

**Architecture in one line:** MMM (strategic: channel budgets) → Agent (tactical:
campaigns, bids, creatives) → Google Ads API, with a human approval gate on every write.

---

## Phase 0 — Access setup (DO TODAY — it's mostly waiting)

Everything below is clicking through Google websites. No code, no cost.

### Step 1 — Google Ads Manager Account (MCC) (~10 min)
1. Go to https://ads.google.com/home/tools/manager-accounts/
2. Sign in with your Google account → "Create a manager account".
3. Name it anything (e.g., "Sameer Agent Lab"). Country/currency: your own.

Why: developer tokens are only issued to *manager* accounts, not regular ad accounts.

### Step 2 — Developer token (~5 min + waiting)
1. In the manager account: **Admin (or Tools & Settings) → API Center**.
2. Fill the API access form (contact email, company name — "personal project" is fine,
   describe use: "in-house campaign analysis and management tooling").
3. You immediately get a token with **test-account-only** access. Copy it somewhere safe.
4. On the same page, apply for **Basic access** (needed later for real accounts).
   Approval = human review at Google, typically days to ~2 weeks. This is the long
   pole — which is why we apply on day 1 and build against test accounts meanwhile.

### Step 3 — Test accounts (~10 min)
1. While signed in, create a **test manager account** from the API Center /
   developers.google.com/google-ads/api/docs/best-practices/test-accounts
2. Under it, create 1–2 test client accounts. These accept campaign creation via API,
   serve nothing, and spend nothing — our sandbox for Phases 1–3.

### Step 4 — Google Cloud project (~15 min)
1. https://console.cloud.google.com → New project → name it `ads-agent`.
2. **APIs & Services → Library** → enable **Google Ads API**.
3. **APIs & Services → OAuth consent screen** → External → fill the minimum fields →
   add your own email as a test user.
4. **Credentials → Create credentials → OAuth client ID** → type "Desktop app".
   Download the JSON. This is how our code will log in as you.

### Step 5 — OpenAI API key (~5 min)
1. https://platform.openai.com → create/sign in → API keys → create key.
2. Add it to `.env` as `OPENAI_API_KEY=...` when you want live LLM planning.
   Without a key, the app uses a deterministic demo planner so the portfolio demo
   still works.

### Phase 0 done when you have:
- [x] Manager account created (2026-07-05: confirmed via `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
      set in `.env`, 10 digits)
- [x] Developer token copied (test access level) (2026-07-05: confirmed set in `.env`)
- [x] Basic access application submitted (2026-07-05: Sameer confirmed submitted;
      Google's review is pending — typically days to ~2 weeks)
- [x] Test manager + test client accounts created (2026-07-05: confirmed via
      `GOOGLE_ADS_CUSTOMER_ID` set in `.env`, 10 digits, the test client account)
- [x] Cloud project with Ads API enabled + OAuth desktop JSON downloaded (2026-07-05:
      ran `scripts/generate_refresh_token.py`, completed the Google consent screen —
      refresh token, client ID, and client secret all confirmed in `.env`)
- [ ] OpenAI API key (still empty in `.env` — optional, demo planner works without it)

Store all secrets in one private note for now; they move to a secrets manager at deploy.

---

## Phase 1 — Local campaign-builder demo (implemented first)

**Deployed to Cloud Run (2026-07-05):** https://mmm-ads-agent-818953231119.us-central1.run.app
(public, no login required — service `mmm-ads-agent`, region `us-central1`,
project `ads-agent-501507`). Still runs locally too:

```bash
conda activate mmm
streamlit run streamlit_app.py
```

What it does:
- Uses the MMM constrained optimizer as the strategic layer.
- Treats `search + display + digital_video` as the Google-controllable budget pool.
- Takes a manual total daily budget and landing page URL.
- Drafts one Search campaign and one Performance Max campaign.
- Defaults every campaign to `PAUSED`.
- Runs in mock mode until `GOOGLE_ADS_MUTATE_ENABLED=true`.
- Writes an audit log for generated plans and approved mock actions.

Implemented files:
- `streamlit_app.py`
- `ads_agent/`
- `tests/test_ads_agent.py`
- `.env.example`
- `Dockerfile`, `requirements-cloudrun.txt`, `.dockerignore`, `.gcloudignore` (Cloud Run deployment)

## Phase 2 — Analyst agent (read-only, zero risk)

Agent tools: `list_campaigns`, `get_performance(date_range)`, `get_search_terms`,
`get_budget_pacing`. The LLM decides which to call to answer questions like
"why did CPA rise last week?" and produces recommendations — but cannot change anything.

Deploy: Google Cloud Run (containerized, real URL, scales to zero ≈ free).
Deliverable: a chat UI (simple web page) your friends/interviewers can try.

**v1 implemented (2026-07-05), still against mock data (real Ads API read access
blocked on Basic access approval, same as Phase 1):**
- `ads_agent/analyst_data.py` — deterministic (seeded) mock campaigns, 14-day daily
  performance, and search terms. Search is modeled with a softening conversion rate
  over the window so CPA visibly rises — the demo scenario for "why did CPA rise."
  Daily cost is pegged to each campaign's own `daily_budget` (+/- pacing noise) so
  budget pacing numbers look like a real account instead of an unrelated multiple.
- `ads_agent/analyst_tools.py` — the four tools as plain functions, plus
  `TOOL_SCHEMAS`/`TOOL_FUNCTIONS` for OpenAI function-calling.
- `ads_agent/analyst_agent.py` — `ask_analyst(question)`: OpenAI tool-calling loop
  when `OPENAI_API_KEY` is set (same fallback pattern as `planner.py`), else
  deterministic keyword routing so the demo works with no key. Read-only — no write
  tool exists anywhere in this file, which is what makes Phase 2 zero-risk.
- Wired into `streamlit_app.py` as an "Ask the analyst" section below the campaign
  planner, with three example-question buttons and a free-text box. Shows which
  tool(s) were called before the answer, for demo transparency.
- `tests/test_analyst_agent.py` — 9 tests covering the 4 tools structurally and all
  3 keyword-routing branches of the fallback path. Full suite: 13/13 passing.
- Verified live in a browser (not just unit tests): booted a second local instance
  on port 8766 (left the pre-existing process on 8765 untouched), clicked all three
  example questions, confirmed correct tool routing and plausible answers. Caught
  and fixed two bugs this way that unit tests didn't catch: (1) dollar signs in the
  answer were rendering as broken LaTeX via `st.write`'s markdown parser — switched
  to `st.text`; (2) mock spend was unrelated to each campaign's budget, producing
  a nonsensical 242% pacing number — fixed by pegging mock cost to `daily_budget`.

**Deployed to Cloud Run (2026-07-05)** alongside Phase 1, same URL:
https://mmm-ads-agent-818953231119.us-central1.run.app — the "Ask the analyst"
section is live there too.

**Bugs found and fixed during first real-key testing (2026-07-05) — both the
campaign planner and analyst agent had never actually been run with a real
OPENAI_API_KEY before this session (it was empty until today), so this was the
first time either OpenAI code path executed at all:**
- `ads_agent/schemas.py`: OpenAI's strict structured-output mode requires
  every object to set `additionalProperties: false` and list *all* its
  properties in `required` (optionality is nullability, not omission) — added
  `model_config = ConfigDict(extra="forbid")` to every schema class, and
  changed `landing_page_url` from Pydantic's `HttpUrl` to a plain `str` with a
  regex pattern (OpenAI's strict mode doesn't support the `"format": "uri"`
  keyword `HttpUrl` generates).
- `ads_agent/planner.py`: added `_to_openai_strict_schema()`, which walks the
  Pydantic-generated JSON schema (including `$defs`) and fixes it up for
  OpenAI's strict-mode requirements — forcing `required` to match `properties`
  on every object, and stripping sibling keys (like Pydantic's `default`) next
  to any `$ref`, which strict mode also forbids.
- `ads_agent/analyst_agent.py`: the tool-calling loop was appending
  `response.output` wrapped in `{"role": "assistant", "content": ...}`, which
  isn't valid for OpenAI's Responses API — function-call output items get
  appended directly to the `input` list, not nested under a role/content
  wrapper. Fixed to `input_messages.extend(response.output)`.
- Verified the fix locally against the real API first (faster iteration than
  redeploying each time), for both the campaign planner and all three analyst
  example questions — confirmed real LLM-generated text with no fallback
  marker, re-ran the full test suite (13/13 still passing), then redeployed to
  Cloud Run and re-verified live in a browser on the public URL.

## Phase 3 — Operator agent (write with approval gate)

Adds tools: `update_budget`, `pause_campaign`, `add_negative_keyword`, etc.
Flow: agent proposes → structured change ticket (what, why, expected impact) →
**you approve/reject in the UI** → only then does it execute → full audit log.

Guardrails (yours to design — this is where your 10 years matter):
- Hard budget cap per change and per day, enforced in code, not in the prompt
- Action allowlist (agent literally has no delete/create-payment tools)
- Dry-run mode: every action can run as a no-op preview first
- Rate limit: max N changes/day
- Kill switch: one env var disables all write tools

**Built and fully verified (2026-07-05)** — deployed alongside Phase 1/2 at
https://mmm-ads-agent-818953231119.us-central1.run.app:
- `ads_agent/guardrails.py` — `validate_action_allowed()` (hardcoded allowlist:
  `UPDATE_BUDGET`, `PAUSE_CAMPAIGN`, `ADD_NEGATIVE_KEYWORD` only),
  `validate_budget_change()` (50% per-change cap **and** the existing absolute
  `max_daily_budget` cap), `check_daily_write_rate_limit()` (20/day, counted
  from the audit log itself so it can't be reset by anything but the day
  rolling over).
- `ads_agent/operator_state.py` — JSON-backed overlay (budget/status/negative
  keywords per campaign) so an approved change actually shows up in later
  Phase 2 analyst answers (`list_campaigns`, `get_budget_pacing`,
  `get_search_terms` all read through it).
- `ads_agent/schemas.py` — `ChangeTicket`/`ChangeAction`: the operator agent's
  only possible output type.
- `ads_agent/operator_agent.py` — `propose_change(request)`. **Only ever
  proposes, never applies** — there is no code path from the LLM's output to
  a mutation. OpenAI structured-output path + deterministic keyword-routed
  fallback, same pattern as `planner.py`/`analyst_agent.py`.
- `ads_agent/google_ads_client.py` — added `update_campaign_budget()`,
  `pause_campaign()`, `add_negative_keyword()` to both `MockGoogleAdsClient`
  and `RealGoogleAdsClient`, all guardrail-checked before doing anything.
- Streamlit "Operator" section: propose → shows the ticket JSON → Approve
  (applies via `get_ads_client()`) / Reject buttons.
- `tests/test_operator.py` — 14 tests (guardrails, mock write methods,
  negative-keyword filtering, fallback routing). Full suite: **27/27 passing**.
- Verified live in a browser, not just unit tests: proposed and approved a
  real budget cut (persisted to `operator_state.json`, showed up in the audit
  log), then proposed a 90%-in-one-shot budget cut and confirmed the code-level
  guardrail blocked it even though the LLM had dutifully proposed exactly what
  was asked — proving the cap lives in code, not the prompt, as designed.
- Bugs caught and fixed during this build: the fallback router matched
  campaign type by checking if the literal string `"performance_max"` was in
  the request text, so "pause the **pmax** campaign" silently matched the
  wrong (Search) campaign — fixed with an explicit pmax/performance-max
  alias check. Also, negative-keyword filtering in `analyst_tools.py`
  originally required an *exact* string match against the search term, so
  adding "free" as a negative didn't filter "free retail products" — fixed
  to a word-boundary regex match, closer to how real broad-match negatives
  behave.

## Phase 4 — Real Google Ads builder (campaign creation end-to-end)
Campaign type selection, structure, RSA headlines/descriptions generation, launch as
PAUSED for your review. Test accounts first, always.

**Built (2026-07-05), UNVERIFIED against a live account** — Sameer's test
accounts (`6844690726`, `3470127543`) were still "not yet enabled" on
Google's side as of this session (a common post-creation activation delay,
not a bug in our credentials/code — see the HANDOFF.md status log for the
full diagnosis, including the discovery that `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
had actually been pointed at the real production "ads-agent" manager account,
not a test account). Since no combination of credentials could reach a live
account, this could only be verified structurally, not against Google's
actual servers:
- `ads_agent/google_ads_builders.py` — real Search campaign creation:
  CampaignBudget → Campaign (`manual_cpc`) → AdGroup → AdGroupCriterion
  (keywords + negatives) → AdGroupAd (responsive search ad). Also a small
  hardcoded language-constant map (English/Spanish/French/German) for basic
  language targeting.
- `ads_agent/google_ads_pmax_builders.py` — real Performance Max creation:
  CampaignBudget → Campaign (`maximize_conversions`) → AssetGroup → text
  assets (headlines/long headlines/descriptions) → **placeholder images**
  generated with PIL (solid color + "PLACEHOLDER" label, sized to Google's
  recommended dimensions: 1200×1200 logo, 1200×1200 square marketing image,
  1200×628 landscape marketing image) uploaded as real image assets and
  linked into the asset group. This is the highest-risk, least-verifiable
  part of the whole project — PMax is one of the most complex campaign types
  in the API, and the placeholders are obviously not real ad creative.
- **Known simplifications**, documented in the code rather than silently
  guessed at: no real geo-targeting criteria (would need a
  `GeoTargetConstantService` name→ID lookup this pass doesn't do — campaigns
  are created with no location restriction); RSA/PMax text truncated to
  Google's character limits (30/90 chars) since `schemas.py` only constrains
  item *count*, not length.
- **Verification actually performed, given no live account access:**
  1. Confirmed every Google Ads API type/service/enum name used
     (`CampaignBudgetOperation`, `AdGroupCriterionOperation`,
     `AssetGroupAssetOperation`, `KeywordMatchTypeEnum`, `AssetFieldTypeEnum`,
     etc.) actually exists in the installed `google-ads` 31.1.0 library
     (API v24) — a pure local lookup, no account needed. This caught one real
     bug: `client.get_type("FieldMask")` doesn't exist (FieldMask is a
     standard protobuf type, not a Google Ads one) — fixed to
     `google.protobuf.field_mask_pb2.FieldMask` in the two operator methods
     that needed an update mask.
  2. Ran the actual builder functions end-to-end with every `mutate_*` RPC
     mocked out but every real protobuf field assignment executed for real —
     catches wrong field names, wrong oneof usage, etc. This caught a second
     real bug: `campaign.url_expansion_opt_out` doesn't exist on the
     `Campaign` message in this API version at all (checked directly against
     the protobuf descriptor) — removed rather than guessing at a
     replacement name.
  3. Generated real placeholder PNGs via PIL during that same structural run
     to confirm the image-generation path itself works, not just the API
     calls around it.
**UPDATE (2026-07-05, same session) — CONFIRMED WORKING END-TO-END, LIVE.**
Once the test account (`4411037941`, under manager `1286821756`) finished
activating, ran `get_ads_client().create_paused_campaigns(...)` for real with
`GOOGLE_ADS_MUTATE_ENABLED=true`. Took 7 rounds of real API errors — every
one of them something the structural (mocked) verification above genuinely
could not have caught — fixed in turn:

1. `client.get_type("FieldMask")` doesn't exist → `google.protobuf.field_mask_pb2.FieldMask`
2. `manual_cpc.enhanced_cpc_enabled` → `OPERATION_NOT_PERMITTED_FOR_CONTEXT`
   (Enhanced CPC restricted for new campaigns) → activate the oneof via
   `campaign.manual_cpc = client.get_type("ManualCpc")` instead
3. `contains_eu_political_advertising` → genuinely required on `Campaign`
   in this API version (added to both builders)
4. `CampaignBudget.explicitly_shared` → new budgets default to shareable,
   incompatible with per-campaign bidding → set explicitly to `False`
5. `DUPLICATE_CAMPAIGN_NAME` → LLM-drafted names aren't unique like the
   demo planner's → added `unique_campaign_name()` (timestamp suffix at
   creation time, a builder-level guarantee)
6. PMax `REQUIRED_BUSINESS_NAME_ASSET_NOT_LINKED` / `REQUIRED_LOGO_ASSET_NOT_LINKED`
   → this account has "Brand Guidelines" enabled → simplest fix was
   `campaign.brand_guidelines_enabled = False`
7. PMax `NOT_ENOUGH_HEADLINE_ASSET` etc. even inside one compound batch →
   Google validates each operation against what precedes it in *submission
   order* → rewrote as a single `GoogleAdsService.mutate()` call with
   temporary negative-numbered resource names, strictly ordered: campaign →
   all assets (incl. a business name text asset — a baseline PMax
   requirement the first draft had missed) → asset group → links, last

**Independently verified after the fact** by querying the account back
(not just trusting a "success" message): both campaigns exist, `PAUSED`,
correct type; Search's ad group has all 7 real keywords; PMax's asset group
has exactly 10 linked assets. Full test suite stayed **27/27 passing**
throughout. Full story with every error message: `HANDOFF.md`'s status log,
2026-07-05 entries.

Known simplifications still standing: no real geo-targeting criteria
(campaigns have no location restriction — harmless for paused test
campaigns, but note before ever enabling one for real); RSA/PMax text
truncated to Google's character limits client-side.

## Phase 5 — Optimizer loop + MMM handshake
Scheduled runs (Cloud Scheduler): pull performance, compare against MMM budget envelope,
auto-execute only small changes within caps, propose the rest. Burn-in on tiny real
budgets for 2+ weeks before trusting it.

**Synthetic precursor built (2026-07-06), not the real-money version above:**
`ads_agent/simulation_state.py` + a scenario ladder in `analyst_data.py` let
`operator_agent.monitor_and_propose()` run proactively against synthetic,
sim-day-indexed data — no real spend, no Cloud Scheduler, no real account. Exposed
in Streamlit as "Simulated optimizer loop," gated by the same human approve/reject
as Phase 3. `ads_agent/evals.py` scores its decisions against a known-correct answer
per scenario (see README's Evals section and HANDOFF.md for what it already found).
This validates the *decision logic*; the real-money burn-in described above is
still a separate, not-yet-started step.

**Expanded 4 → 14 scenarios (2026-07-06, same day):** built from
`docs/EVAL_EXPANSION_SPEC.md`, a scoped-down implementation of the full 60-scenario
catalog in `docs/EVAL_SCENARIOS.md` (see `docs/EVAL_SCOPE_DECISIONS.md` for which 14
and why). Fixed one real ground-truth bug in the process: the original
`budget_overrun` scenario treated a single day at 1.4x daily budget as a problem,
but Google Ads legitimately allows up to ~2x daily overdelivery — that scenario was
rewritten as two: `single_day_overdelivery` (1.6x for one day, correctly no action)
and `sustained_overrun` (>=3 of the last 5 days over 1.25x, correctly a budget cut).
The other 10 new scenarios cover: a near-miss CPA ratio and a low-volume statistical
fluke (restraint traps), a zero-click keyword guard, a conversion-tracking-breakage
trap (the classic "don't mass-pause a healthy account" case), a root-cause-vs-symptom
discrimination test (exclude the one keyword causing a CPA spike, don't pause the
whole campaign), a budget-limited-winner case (the agent must be able to propose
raising a budget, not just cutting one), missing-data and empty-account degenerate
inputs, and a prompt-injection attempt embedded directly in a search term's text.
Deterministic reference implementation: **14/14**, every run. See HANDOFF.md for
the real LLM-path result this run produced.

**This is Level 1 of a 4-level eval-coverage roadmap, deliberately** — 14 of the
60 cataloged scenarios, chosen for decision-category coverage over raw count (see
README's "Eval coverage maturity" table and `docs/EVAL_SCOPE_DECISIONS.md` for the
full backlog). Level 2 (remaining restraint traps, keyword/cannibalization variants,
multi-signal conflicts) needs no new simulation modeling, just more data authoring.
Level 3 (Ad Rank / Quality Score scenarios) needs new simulator fields (QS,
impression-share-lost-to-rank) and agent actions that don't exist yet. Level 4 (all
18 Meta scenarios) needs the ad-set/ad entity-hierarchy refactor Meta's real-write
path will need anyway — not started, and lower priority while Meta Ads' real-API
path is separately blocked on the payment-method/region issue in
`META_ADS_AGENT_PLAN.md`.

## Phase 7 — Autonomous initiation + eval-gated tiered autonomy (planned, not started)

Full implementation spec: `docs/L4_AUTONOMY_SPEC.md` (written for "Claude Code
(implementing agent)", same format as `docs/EVAL_EXPANSION_SPEC.md`); plain-English
companion: `docs/L4_AUTONOMY_EXPLAINED.md`. Added to this plan on 2026-07-06 as
documented scope only — no code has been written for this yet.

**What it would move**, in one line: the operator agent currently only runs when a
human clicks "Check account" (Phase 5's simulated loop) or asks it a question (Phase
3). This spec would let it start its own monitoring cycles, remember what it
proposed across runs (and not repeat/escalate accordingly), and — only for
`ADD_NEGATIVE_KEYWORD`, only if `AUTONOMY_ENABLED=true` (default `false`), and only
while the latest eval run (`docs/EVAL_EXPANSION_SPEC.md`'s harness) shows that
specific action passing every relevant scenario at full k/k consistency — apply that
one low-risk, reversible action class without a human click first. `UPDATE_BUDGET`
and `PAUSE_CAMPAIGN` are hardcoded high-risk forever in the spec and never become
auto-applicable.

**Mandatory honest-labeling rule, carried over from the spec itself:** this work
does **not** make the system "L4." The correct description afterward is **"L3 +
autonomous initiation + eval-earned auto-apply for one action class"** — never
"fully autonomous." Any README/docs update from this phase must use that exact
phrasing, matching this repo's existing discipline about not overselling agent
levels.

**Four parts, in the spec's own build order** (A2→A1→A4→B→C→D; C is inert until
eval runs exist, D is independent and droppable):
- **Part A** — a scheduled/on-demand monitoring cycle (`ads_agent/autonomous_run.py`), a proposal queue with dedupe, and an optional Slack notify adapter. Adds a "Proposal Inbox" to Streamlit.
- **Part B** — outcome memory across cycles (`ads_agent/run_history.py`): tags each prior proposal `resolved`/`unresolved`/`too_early` and feeds that history back into both the LLM prompt and the deterministic rules so the agent doesn't repeat a rejected or still-pending action, and escalates (e.g. budget cut → pause) when a prior fix didn't work.
- **Part C** — the eval-gated auto-apply policy (`ads_agent/autonomy_policy.py`) described above, with an undo affordance in the inbox for anything auto-applied.
- **Part D** — an MMM drift monitor (`ads_agent/mmm_drift.py`) comparing actual spend share per channel against the MMM's recommended split, proposing a rebalancing `UPDATE_BUDGET` ticket (always approval-gated, never auto-applied) when drift exceeds 10 points.

**Global constraints the spec itself sets, worth preserving if this gets built:**
mock mode stays the default everywhere; every new write still goes through the
single existing `apply_change_ticket` path (no second write path introduced); every
new behavior emits an audit event; all new state files follow the existing
JSON/JSONL-in-`ads_agent/` pattern with `tests/conftest.py`-style cleanup.

## Stretch goal — Shopping campaigns
Not scoped into any phase above yet. v1 only supports Search + Performance Max
(PMax already covers Display/YouTube/Discover/Gmail inventory, so a standalone
Display campaign type was deliberately skipped — it would mostly cannibalize PMax's
own inventory rather than add capability).

Shopping is the one genuinely missing format worth considering later: the MMM dataset
is framed as a retailer selling physical products, so a Shopping campaign (or PMax
fed by a Shopping feed) would be the most realistic real-world extension of the
"MMM → media plan" story. Blocked on a Google Merchant Center product feed, which
doesn't exist yet and is its own separate setup — not part of Phase 0. Revisit only
if/when the portfolio story specifically calls for it; not needed for the Basic
access application (kept out of DESIGN_DOCUMENTATION.md and the Q11/Q12 answers on
purpose, to keep that submission matched to what's actually built).

---

## Timeline (realistic)
- Today: Phase 0 steps 1–5 (~45 min active) + Basic access application submitted
- Flow week: Phases 1–2 built and deployed against test accounts
- When Basic access arrives: point Phase 1 (read-only!) at a real account
- +2–3 weeks: Phase 3, then guarded Phase 4

## Status log
- 2026-07-03: Plan created. Phase 0 pending.
- 2026-07-04: Local Streamlit v1 implemented in mock mode. It creates editable,
  approval-gated Search + PMax campaign drafts from the MMM digital budget envelope.
  Tests pass (`4 passed`). Phase 0 credentials still pending before real Google Ads
  API mutation can be safely enabled.
- 2026-07-06: Built a synthetic-data precursor to Phase 5 (see that section above) --
  `ads_agent/simulation_state.py`, a 4-scenario ladder in `analyst_data.py`,
  `operator_agent.monitor_and_propose()`, and `ads_agent/evals.py`, the first real
  eval harness in this repo (scores decisions against a known-correct answer, not
  just code correctness). Full detail, including a real LLM decision-quality gap the
  harness caught, in `HANDOFF.md`. 45/45 tests passing.
- 2026-07-06 (same day): Expanded the eval ladder from 4 to 14 scenarios per
  `docs/EVAL_EXPANSION_SPEC.md` (see that section above for what's new). Fixed a
  real ground-truth bug (the old budget_overrun scenario penalized normal Google
  Ads overdelivery). Deterministic path: 14/14. Full test suite: 60/60 passing.
  See `HANDOFF.md` for the full LLM-path result this expansion surfaced.
- 2026-07-06 (same day): Added Phase 7 (autonomous initiation + eval-gated tiered
  autonomy) to this plan as **documented scope only** -- Sameer asked to add
  `docs/L4_AUTONOMY_SPEC.md` to the project's scope; confirmed with him this meant
  planning, not building, before touching any code. See the Phase 7 section above.
  No code written for this yet.
