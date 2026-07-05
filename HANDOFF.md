# HANDOFF — Read this first (context for any new Claude session)

If you are Claude starting fresh: read this file, then README.md and
GOOGLE_ADS_AGENT_PLAN.md. That's the full context. Skim docs/LEARNING_GUIDE.md to see
the teaching style that works.

This file was rewritten from scratch on 2026-07-05 after a Codex CLI session was
asked to produce this handoff and silently failed twice (empty responses, no file
changes — see "Note on the Codex session" at the bottom). Everything below was
re-verified against the live repo, not copied blind from the previous version.

## Who Sameer is
- Marketer, ~10 years running ads — deep domain knowledge, a bit dated - so help me brush up and guide him so we can collectively succeed
- MBA student (IPMX). This is a placement/portfolio project.
- Does NOT code. Python is rusty/minimal. All code must be written for him,
  heavily commented, with exact copy-paste commands. Never assume he can debug alone.
- Learns best from STORIES FIRST, formula last. What worked: pizza-shop story for
  adstock, town-of-50,000 for saturation, cake-mix analogy for libraries. What failed:
  leading with formulas or jargon. If he says "I'm not understanding at ALL," change
  the explanation entirely — don't repeat it slower.
- Goes into extended flow states; give him meaty, sequential step-by-step tracks.

## Repo layout (every file, what it's for)

```
/AGENTS.md                     — Codex-specific working instructions (mirrors this file's "how to work with him" section)
/HANDOFF.md                    — this file
/GOOGLE_ADS_AGENT_PLAN.md      — full Track 2 (Google Ads) build plan + its own status log
/META_ADS_AGENT_PLAN.md        — Track 2 Phase 6 (Meta Ads) build plan + its own status log
/README.md                     — project overview / setup for a human reader
/LICENSE                       — MIT
/requirements.txt              — pinned deps, see "Environment" below
/streamlit_app.py              — Track 2 v1 UI (Streamlit)
/.env.example                  — template for local .env (no real .env exists yet — mock mode only)
/.gitignore                    — excludes .env, .cache/, __pycache__, audit_log.jsonl, etc.

/docs/                         — supplementary docs, kept out of the root to keep it scannable
  LEARNING_GUIDE.md            — teaching-style notes (story-first explanations used so far)
  MMM_Project_Guide.pdf        — generated study guide (PDF)
  MMM_Study_Guide.html         — generated study guide (interactive HTML)
  DESIGN_DOCUMENTATION.md      — Google Ads Basic Access application submission doc (kept matched to what's actually built)

/data/
  DATA_DICTIONARY.md           — channel definitions/grouping rationale
  raw_data.csv                 — downloaded by notebook 01 (exists, from the 2026-07-03 run)
  model_data.csv               — cleaned/grouped table notebook 01 saves for notebook 02 (exists)

/notebooks/
  01_data_exploration.ipynb    — Track 1 step 1 (see status below)
  02_build_mmm.ipynb           — Track 1 step 2 (see status below)
  .ipynb_checkpoints/          — autosave checkpoints, ignore

/ads_agent/                    — Track 2 v1 package
  __init__.py
  budget.py                    — MMM_RECOMMENDED_WEEKLY constants + calculate_google_ads_split()
  schemas.py                   — pydantic models: CampaignPlan, CampaignDraft, Keyword, SearchAdDraft, PMaxAssetDraft, enums
  planner.py                   — generate_campaign_plan(): OpenAI path (if OPENAI_API_KEY set) with deterministic-planner fallback
  guardrails.py                — GuardrailError + validate_plan_for_paused_creation() / validate_enable_request()
  google_ads_client.py         — MockGoogleAdsClient (default) / RealGoogleAdsClient (blocked until Phase 0 + explicit env flag) / get_ads_client()
  audit.py                     — write_audit_event() → appends to audit_log.jsonl
  audit_log.jsonl              — append-only log of every plan generated / mock action taken (gitignored, currently has 4 entries from testing)
  placeholder_images.py        — generate_placeholder_image(): shared by the Google PMax and Meta builders (no real ad creative in this project)
  meta_schemas.py              — Phase 6: pydantic models for Meta campaign plans, mirrors schemas.py's shape for Meta's Campaign->Ad Set->Ad structure
  meta_planner.py              — Phase 6: generate_meta_campaign_plan(), same OpenAI/fallback pattern as planner.py
  meta_ads_client.py           — Phase 6: MockMetaAdsClient / RealMetaAdsClient (UNVERIFIED) / get_meta_ads_client()
  meta_ads_builders.py         — Phase 6: real Meta Marketing API calls via facebook-business SDK (UNVERIFIED, no Meta account exists yet)

/tests/
  conftest.py                  — pytest fixtures (see below)
  test_ads_agent.py            — 4 tests, all passing as of this session

/.cache/                       — jupyter/matplotlib/arviz cache dirs, ignore
/.pytest_cache/                — ignore
```

## The two projects (one folder, two tracks)

### Track 1 — Bayesian MMM (primary, weeks 1–4)

**Stack:** PyMC-Marketing **0.15.1** (pinned in requirements.txt; all notebook-02 API
calls verified against it). Chosen over Robyn (ridge + evolutionary search, hard to
defend in interviews) and Meridian (geo-hierarchical, our data is national-level).

**Data:** real anonymized US retailer, 200+ wks 2014–18, from github.com/sibylhe/mmm_stan.
Notebook 01 downloads it. 10 spend channels grouped into 7 (see data/DATA_DICTIONARY.md):
tv, social, audio, digital_video, display, search, print_mail.

**Workflow:** notebooks/01_data_exploration.ipynb → notebooks/02_build_mmm.ipynb.

**Notebook 01 status (verified this session by reading the saved .ipynb JSON directly —
no execution errors in any cell output):**
- Runs clean end-to-end. `data/raw_data.csv` and `data/model_data.csv` exist on disk.
- 15 cells total. The last real cell (#13, markdown) is titled "My observations (fill
  this in!)" and is **still the blank template** — bullets like "Biggest channel by
  spend: ..." are unfilled. Sameer has not done this yet. This is homework for him, not
  a bug — don't fill it in for him, that defeats the point (habit-building, per cell 11's
  own text: "that habit is what turns a tutorial into *your* project").

**Notebook 02 status (verified this session — read the saved outputs directly, no error
outputs anywhere in the notebook):**
- The budget-optimizer cell (cell 14) was previously patched to correctly unpack
  `allocation, opt_result = mmm.optimize_budget(...)` (returns a tuple, not a single object).
- It uses **realistic planning bounds**, not an unconstrained optimum — per-channel
  multipliers on the trailing-52-week average spend:
  - tv: 0.60–2.50x, digital_video: 0.50–4.00x, search: 0.70–1.75x, social: 0.60–1.75x,
    display: 0.60–1.50x, audio: 0.60–1.75x, print_mail: 0.50–0.85x (deliberately forces
    a controlled cut — it's the highest-spend, lowest-ROI channel).
- **Actual verified output** (this is the real, already-executed result sitting in the
  notebook, cross-checked line-by-line against `ads_agent/budget.py`'s hardcoded
  constants — they match exactly, nothing was fabricated):

  | channel        | current weekly $ | recommended weekly $ | change % |
  |----------------|-------------------|------------------------|----------|
  | tv             | 136,500           | 317,823                | +132.8%  |
  | social         | 175,997           | 307,995                | +75.0%   |
  | audio          | 127,248           | 222,684                | +75.0%   |
  | digital_video  | 21,379            | 85,517                 | +300.0%  |
  | display        | 281,534           | 317,823                | +12.9%   |
  | search         | 722,419           | 521,581                | -27.8%   |
  | print_mail     | 648,471           | 340,124                | -47.5%   |

  Avg weekly media budget (last 52 wks): $2,113,548. Feasible range the optimizer
  worked within: $1,273,386–$3,195,181. Optimizer converged: True.
- Cell 5 (`mmm.fit(...)`) is a 10–40 minute MCMC sampling step run locally by Sameer.
  That's expected, not a hang — don't "fix" it by cutting chains/draws without telling
  him, since that changes the statistical validity of the result.

**Stretch goals agreed (not started):** holdout validation, Robyn comparison, Meridian
geo model using Google's simulated dataset
(raw.githubusercontent.com/google/meridian/refs/heads/main/meridian/data/simulated_data/csv/geo_all_channels.csv
— verified reachable: geo, time, 5 channels impressions+spend, controls, conversions,
revenue_per_conversion, population).

### Track 2 — Google Ads agent (secondary, after MMM or in parallel waiting time)

Full plan in GOOGLE_ADS_AGENT_PLAN.md, including Phases 2–5 which are **not built yet**
(only Phase 1 exists). Phase 0 (accounts/tokens) — checklist in that file is entirely
unchecked; no `.env` file exists in the repo (only `.env.example`), so the app is
running in mock mode only. Ask Sameer directly what's changed since, don't assume.

**Architecture:** MMM = strategic layer (budget envelope) → agent = tactical layer
(campaigns) → Google Ads API, human approval gate on every write. Not yet on
LangGraph — v1 is a straight Streamlit + pydantic + function-call flow, no agent
framework wired in yet. Not deployed — runs on localhost only right now, not Cloud Run.

**Honest framing agreed:** MMM is classical statistics, NOT AI — the agent is the
agentic piece. Don't let him oversell one as the other in interviews.

**Verified working this session** (I ran it live, not just the unit tests):
1. `streamlit run streamlit_app.py` boots clean, no errors, on `http://localhost:8765`.
2. Filled in the default form (Anonymized Retailer / $100 daily budget / example.com),
   clicked "Generate plan" → correctly produced one PAUSED Search campaign
   ($56.39/day) and one PAUSED Performance Max campaign ($43.61/day), split
   56.4%/43.6% — matches `calculate_google_ads_split()`'s math off the MMM pool
   (search=$521,581/wk vs display+digital_video=$403,340/wk from the table above).
3. Clicked "Create paused campaigns" → guardrails passed (budget under the $1,000
   cap, statuses PAUSED, PMax had asset drafts) → wrote a real entry to
   `ads_agent/audit_log.jsonl` → UI showed "Mock campaigns created as paused
   audit-log entries."
4. `pytest tests/` → **4 passed** in 0.08s:
   - `test_budget_split_preserves_mmm_google_ads_proportions`
   - `test_demo_planner_generates_search_and_pmax_plan`
   - `test_guardrail_rejects_budget_over_cap`
   - `test_mock_client_logs_paused_creation`

**Not yet built:** Phase 2 (read-only analyst agent tools: `list_campaigns`,
`get_performance`, `get_search_terms`, `get_budget_pacing`), Phase 3 (write tools with
approval gate), Phase 4 (real campaign creation end-to-end), Phase 5 (scheduled
optimizer loop). All of these need Phase 0 credentials first (dev token, OAuth client,
test accounts) — none of which exist yet.

## Environment

- Local conda env named `mmm`, Python 3.11.15. Activate: `conda activate mmm`.
- Install/refresh deps: `pip install -r requirements.txt` from repo root.
- **Do not bump `pymc` off `5.23.0`** without re-testing. Plain
  `pip install -r requirements.txt` normally pulls the newest pymc (5.25+), which
  renamed `pymc.logprob.utils.rvs_in_graph` — that breaks notebook 02's budget
  optimizer import with `ImportError: cannot import name 'rvs_in_graph'`. The pin
  in requirements.txt (`pymc==5.23.0` alongside `pymc-marketing==0.15.1`) is the
  tested-working combo. This is the single most important gotcha in the repo.
- No `streamlit` version is pinned. If a future upgrade deprecates
  `st.dataframe(..., use_container_width=True)` (used in streamlit_app.py), that's a
  one-line fix (`width="stretch"`), not a real bug — check the installed version
  before "fixing" phantom issues.

## Resume commands

```bash
conda activate mmm

# Track 1
jupyter lab notebooks/01_data_exploration.ipynb   # fill in the observations cell
jupyter lab notebooks/02_build_mmm.ipynb          # already run once; re-run if data changes

# Track 2
streamlit run streamlit_app.py                    # local, mock mode + real OpenAI if .env has a key
pytest tests/ -v

# Track 2, redeploy after a code change (rebuilds via Cloud Build, no local Docker needed)
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
gcloud run deploy mmm-ads-agent --source . --region=us-central1 --project=ads-agent-501507 \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_ADS_MUTATE_ENABLED=false,MAX_DAILY_BUDGET_USD=1000,OPENAI_MODEL=gpt-4.1-mini \
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest
```

**Live public demo:** https://mmm-ads-agent-818953231119.us-central1.run.app
(Cloud Run, `ads-agent-501507` project, `us-central1`, public/no login).

## Resume bullet he's building toward
"Built a Bayesian Marketing Mix Model (PyMC-Marketing) on 4 years of weekly retail data
across 10 media channels; quantified channel ROI with uncertainty intervals and
recommended a budget reallocation projected to lift revenue X% at constant spend."
Plus: "Built an agentic Google Ads analyst/operator on top with human-in-the-loop
approval, deployed on Cloud Run."

## Immediate next steps (pick up here)
1. Sameer: fill in notebook 01's "My observations" cell (still blank).
2. Phase 0 is done except waiting on Google's Basic access review — nothing to
   do there but wait.
3. Phases 1–3 are built, tested, and deployed live on Cloud Run:
   https://mmm-ads-agent-818953231119.us-central1.run.app. Phase 4 (real
   campaign creation) is also built but **unverified** — blocked purely on
   Sameer's Google Ads test accounts finishing activation (see status log).
4. **The one thing actually blocking further progress right now**: keep
   checking whether `6844690726` / `3470127543` (the test manager/client
   accounts) have moved past "not yet enabled." Once they have, the very
   next step is: set `GOOGLE_ADS_MUTATE_ENABLED=true` locally, run
   `pytest`-style structural confidence aside, actually click "Create paused
   campaigns" in the Streamlit UI against the real test account, and expect
   to debug the Performance Max path specifically — it's flagged in
   GOOGLE_ADS_AGENT_PLAN.md as the least certain part of the whole build.

## Status log (update me as things complete!)
- 2026-07-03: Project scaffolded, guides built (HTML interactive + PDF), pymc-marketing
  0.15.1 verified. Sameer has NOT yet: installed conda / run notebook 01 / done Phase 0
  of the Ads plan.
- 2026-07-03 (later): Claude test-ran the whole install + notebook 01 pipeline in a
  sandbox to de-risk it. Found and fixed the pymc 5.25+ / `rvs_in_graph` import break;
  pinned pymc==5.23.0. Fixed notebook 02's budget-optimizer tuple-unpack bug. Notebook 01
  executed end-to-end — real findings: print_mail is 46.5% of media spend (dominant
  channel), then search 26.7%, display 9.2%, tv 7.2%, audio 5.4%, social 4.3%,
  digital_video 0.8%. No channel pairs correlate above ~0.6.
- 2026-07-04: Notebook 02 completed locally; optimizer patched with realistic channel
  bounds (see table above). Google Ads agent v1 implemented as a local Streamlit app in
  mock mode (`streamlit_app.py`, `ads_agent/`, `.env.example`, tests). Tests pass
  (4 passed). Google Ads Phase 0 credentials still needed before real API mutation.
- 2026-07-05, ~01:31 local: A Codex CLI session was asked twice, verbatim, to "give an
  ultra-detailed and elaborate handoff document to claude-code for transferring the
  project - leave nothing out." Both times Codex returned a **completely empty
  response** (`last_agent_message: null`, no tool calls, no file writes) after ~2
  seconds each — a silent failure, not a wrong answer. No file in the repo was touched.
  The user gave up and exited that session.
- 2026-07-05 (this session): Claude was asked to assess the Codex failure and pick up
  from there. Diagnosed the empty-response failure directly from
  `~/.codex/sessions/2026/07/05/rollout-2026-07-05T01-30-31-*.jsonl`. Re-verified the
  entire repo state first-hand rather than trusting prior docs: ran `pytest` (4/4
  pass), launched `streamlit_app.py` live and clicked through the full Generate Plan →
  Create Paused Campaigns flow in a browser (works, guardrails fire correctly, audit
  log entry written), and cross-checked notebook 02's actual optimizer output against
  `ads_agent/budget.py`'s hardcoded constants (exact match, not fabricated). Rewrote
  this file to be the ultra-detailed handoff Codex failed to produce.
- 2026-07-05 (later, ~12:58 local): Sameer started Google Ads Phase 0. Ran
  `scripts/generate_refresh_token.py` against a downloaded OAuth Desktop client JSON;
  completed Google's consent screen (Cloud project + OAuth client from Step 4 exist).
  Cleared the terminal before copying the token, so had to rerun the script once more
  (same client JSON, still on disk at `~/Downloads/client_secret_...apps.googleusercontent.com.json`)
  — reran successfully. Created `.env` from `.env.example` (didn't exist before) and
  confirmed `GOOGLE_ADS_REFRESH_TOKEN` is now set (128 chars) via a length-only check,
  no secret value printed. Checked off Step 4 in GOOGLE_ADS_AGENT_PLAN.md's Phase 0
  list. Still empty in `.env` / still needed: `GOOGLE_ADS_DEVELOPER_TOKEN`,
  `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `GOOGLE_ADS_CUSTOMER_ID`, `OPENAI_API_KEY`. Steps
  1–3 (manager account, dev token, test accounts) still unconfirmed/unchecked.
- 2026-07-05 (later still): Extracted `client_id`/`client_secret` directly from the
  downloaded OAuth Desktop JSON (`~/Downloads/client_secret_...json`) via a one-off
  script and wrote them into `.env` — confirmed set (72 and 35 chars respectively) by
  length-only check, no secret values printed anywhere. `.env` now has: OPENAI_MODEL,
  GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN,
  GOOGLE_ADS_MUTATE_ENABLED, MAX_DAILY_BUDGET_USD all set. Still empty: OPENAI_API_KEY,
  GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID, GOOGLE_ADS_CUSTOMER_ID —
  all blocked on Phase 0 Steps 1–3 (manager account → developer token → test
  accounts), which Sameer has not started yet.
- 2026-07-05 (later still): Sameer completed Phase 0 Steps 1–3 (manager account,
  developer token, test manager + test client accounts). Filled in
  GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID (manager account, 10
  digits, no dashes), and GOOGLE_ADS_CUSTOMER_ID (test client account, 10 digits —
  had to strip dashes from the format Google's UI shows). All confirmed set via
  length/format-only checks, no secret values ever printed. `.env` now has every
  Google Ads field except `OPENAI_API_KEY` (optional). Checked off the corresponding
  boxes in GOOGLE_ADS_AGENT_PLAN.md's Phase 0 list. Sameer confirmed the Basic access
  application (Step 2) was submitted too — now waiting on Google's review (days to
  ~2 weeks). **Phase 0 is fully checked off** (only `OPENAI_API_KEY` optional field
  remains empty). `RealGoogleAdsClient` in
  `google_ads_client.py` is still just a guarded placeholder (raises
  NotImplementedError) so nothing can mutate real/test accounts yet — that's Phase 2+
  work, not a Phase 0 gap.
- 2026-07-05 (Phase 2 v1 built): Implemented the read-only analyst agent —
  `ads_agent/analyst_data.py` (seeded mock campaigns/performance/search terms, cost
  pegged to each campaign's own daily_budget), `ads_agent/analyst_tools.py` (the 4
  tools + OpenAI TOOL_SCHEMAS), `ads_agent/analyst_agent.py` (`ask_analyst()`:
  OpenAI tool-calling loop with a deterministic keyword-routed fallback, same
  no-key-still-works pattern as `planner.py`). Wired into `streamlit_app.py` as an
  "Ask the analyst" section. Added `tests/test_analyst_agent.py` (9 new tests).
  Full suite: **13/13 passing**. Verified live, not just unit tests: ran a second
  Streamlit instance on port 8766 (didn't touch the existing process already
  running on 8765), clicked through all three example questions in a real browser.
  Found and fixed two bugs that only showed up live: dollar signs in answers were
  rendering as broken LaTeX (`st.write` → `st.text`), and mock spend was unrelated
  to campaign budget, producing a nonsensical 242% pacing figure (fixed by pegging
  mock cost to `daily_budget`). Re-verified both fixes live after restarting the
  test server (code changes don't hot-reload without the `watchdog` package
  installed — a plain page refresh isn't enough, the process itself needs a
  restart). Still on mock data and localhost only; not deployed to Cloud Run.
- 2026-07-05 (Cloud Run deployment): Sameer added a real `OPENAI_API_KEY` to
  `.env` (Phase 0's last optional field). Installed the `gcloud` CLI (no
  brew/Docker on this machine — `gcloud run deploy --source .` builds
  remotely via Cloud Build, so local Docker was never needed), authenticated
  as `sameer261h@gmail.com`, confirmed billing enabled on the `ads-agent`
  project (`ads-agent-501507`), enabled the Cloud Run/Cloud Build/Artifact
  Registry/Secret Manager APIs, stored `OPENAI_API_KEY` in Secret Manager
  (never baked into the image), and wrote `Dockerfile` +
  `requirements-cloudrun.txt` (a slim dependency set — the full
  `requirements.txt` also pulls in pymc/arviz/jupyterlab for the Track 1
  notebooks, which the deployed Streamlit app doesn't need) + `.dockerignore`
  + `.gcloudignore` (so `.env` and secrets are never uploaded to Cloud Build).
  Deployed to Cloud Run: **https://mmm-ads-agent-818953231119.us-central1.run.app**
  (public, `--allow-unauthenticated`; no Google Ads secrets deployed since
  `RealGoogleAdsClient` is still just a placeholder).

  First real-key test (in the browser, on the live deploy) surfaced that the
  campaign-plan rationale text was byte-for-byte identical to the demo
  planner's hardcoded strings — a dead giveaway the OpenAI call was silently
  failing and falling back. Found the actual error via `find`/`javascript_tool`
  on the rendered page (`fallback used: Error code: 400 ...`) and fixed three
  real, pre-existing bugs in the OpenAI integration — **neither `planner.py`
  nor `analyst_agent.py`'s OpenAI code path had ever actually run before this
  session**, since `OPENAI_API_KEY` was empty until today:
  1. `ads_agent/schemas.py` — OpenAI's strict structured-output mode requires
     `additionalProperties: false` and *every* property listed in `required`
     (optionality is nullable types, not omission); added
     `model_config = ConfigDict(extra="forbid")` to every schema class.
  2. Same file — `landing_page_url: HttpUrl` generates a `"format": "uri"`
     keyword OpenAI's strict mode rejects; changed to `str` with a regex
     pattern.
  3. `ads_agent/planner.py` — added `_to_openai_strict_schema()` to walk the
     generated schema (incl. `$defs`) and strip sibling keys next to any
     `$ref` (strict mode forbids keys like Pydantic's `default` next to a
     `$ref`), on top of the `required`/`additionalProperties` fix.
  4. `ads_agent/analyst_agent.py` — the tool-calling loop wrapped
     `response.output` in `{"role": "assistant", "content": ...}`, which
     isn't valid for the Responses API; function-call output items must be
     appended directly to `input`. Fixed to `input_messages.extend(response.output)`.

  Verified each fix locally against the real OpenAI API first (faster than
  redeploying every time) — confirmed real LLM-generated text with no
  fallback marker for the campaign planner and all three analyst example
  questions, re-ran the full test suite (**13/13 still passing**), then
  redeployed to Cloud Run (revision `mmm-ads-agent-00002-ctx`) and
  re-verified live in a browser on the public URL — real, non-fallback output
  confirmed there too.
- 2026-07-05 (Phase 3 + Phase 4 built in one session, at Sameer's request to
  "finish 3 and 4 today"): Refactored `_to_openai_strict_schema` out of
  `planner.py` into a shared `ads_agent/openai_schema_utils.py`
  (`to_openai_strict_schema`) since the new operator agent needs the same
  strict-schema fixup.

  **Attempted live-API verification first, as always** — before building
  anything, ran a real read-only query (`SELECT customer.id ... FROM
  customer`) against `GOOGLE_ADS_CUSTOMER_ID`. It failed with
  `CUSTOMER_NOT_ENABLED`. Diagnosed further via `ListAccessibleCustomers`:
  the credentials can actually see three accounts (`6844690726`,
  `3470127543`, `9679627182`), but `9679627182` turned out to be the real
  production "ads-agent" manager account (dev token is test-only, so it's
  correctly blocked from it), and the other two — the actual test
  manager/client accounts from Phase 0 — both return "not yet enabled or has
  been deactivated" no matter which is used as the login-customer-id header.
  This is a normal post-creation activation delay on Google's side (minutes
  to hours), not a bug in our credentials or code. Also found
  `GOOGLE_ADS_CUSTOMER_ID` in `.env` didn't match *any* accessible account —
  a copy-paste typo Sameer then fixed. Given this, agreed with Sameer to
  build both phases now and defer live verification to whenever the test
  account activates.

  **Phase 3 (operator agent, write with approval gate) — built AND fully
  verified**, since it only needs the existing mock data layer:
  - `guardrails.py`: budget-change cap (50% per-change, on top of the
    existing absolute cap), daily write rate limit (20/day, counted from the
    audit log), action allowlist.
  - `operator_state.py`: JSON-backed overlay so approved changes show up in
    Phase 2's analyst answers too (`list_campaigns`, `get_budget_pacing`,
    `get_search_terms`).
  - `schemas.py`: added `ChangeTicket`/`ChangeAction`.
  - `operator_agent.py`: `propose_change()` — only ever proposes, never
    applies; OpenAI structured output + deterministic fallback.
  - `google_ads_client.py`: added `update_campaign_budget`/`pause_campaign`/
    `add_negative_keyword` to both Mock and Real clients.
  - Streamlit "Operator" section wired in.
  - `tests/test_operator.py`: 14 new tests. Full suite: **27/27 passing**.
  - Verified live in a browser: approved a real budget cut (persisted,
    audit-logged), then confirmed the code-level 50% guardrail actually
    blocked a 90%-cut request even though the LLM dutifully proposed exactly
    what was asked — the cap lives in code, not the prompt.
  - Two bugs caught live and fixed: the deterministic fallback matched
    campaign type by checking for the literal substring `"performance_max"`,
    so "pause the **pmax** campaign" silently targeted the wrong (Search)
    campaign — fixed with an explicit alias check. Negative-keyword
    filtering in `analyst_tools.py` required an *exact* string match against
    the search term, so adding "free" didn't filter "free retail products" —
    fixed to a word-boundary regex match.
  - Redeployed to Cloud Run (revision `mmm-ads-agent-00003-rxm`) and
    re-verified the Operator flow live on the public URL.
- 2026-07-05 (later still): Resolved the `CUSTOMER_NOT_ENABLED` mystery from
  earlier today. Set up an hourly background check (session-local, via
  ScheduleWakeup — a cloud-based `/schedule` routine was considered and
  rejected because it can't access local `.env` secrets) to re-poll
  `6844690726` / `3470127543` for activation. Sameer then clarified **both
  accounts are actually cancelled** — explaining the persistent error message
  in full: "not yet enabled **or has been deactivated**" was accurate the
  whole time, not a temporary provisioning delay. Stopped the hourly check
  (waiting longer was never going to help).

  **Redid Phase 0 Step 3 properly**, this time confirming with Google Ads
  API support directly (an email from "James," quoted in full in this
  session) that a genuinely new test manager account must be created via the
  standard manager-accounts page (`ads.google.com/home/tools/manager-accounts/`
  — the same flow used for the real "Sameer Agent Lab" account), then a test
  client account created *from inside* that new manager account (via
  Accounts → + → Create new account), which automatically makes it a test
  account. Created "MMM Test Manager" (`2676053905`) and a test client
  account (`7416088297`) under it — confirmed the client-account creation
  form did **not** ask for billing info, which the official docs flag as the
  expected (not erroneous) behavior for a real test sub-account. Updated
  `.env`: `GOOGLE_ADS_LOGIN_CUSTOMER_ID=2676053905`,
  `GOOGLE_ADS_CUSTOMER_ID=7416088297`. `ListAccessibleCustomers` confirms
  `2676053905` is visible to our credentials (new, not present before), but
  both it and `7416088297` still return `CUSTOMER_NOT_ENABLED` as of this
  session — expected for an account created minutes ago, unlike the old
  cancelled accounts where this same error was permanent. Restarted the
  hourly background activation check (session-local via ScheduleWakeup)
  against the corrected IDs. That account (`7416088297` under
  `2676053905`) never did activate during this session — see what actually
  unblocked things below.

  **RESOLVED, same session, ~2 hours later:** Sameer had created yet another
  test account, this time from a brand new Google login
  (`sameer.ads.test@gmail.com`) rather than `sameer261h@gmail.com` — so our
  existing refresh token had no permission on it at all (`User doesn't have
  permission to access customer`, a different error than
  `CUSTOMER_NOT_ENABLED`). Regenerated `GOOGLE_ADS_REFRESH_TOKEN` via
  `scripts/generate_refresh_token.py`, this time completing the consent
  screen as `sameer.ads.test@gmail.com`. (Along the way, fixed a corrupted
  `.env` line — the pasted refresh token had merged with the next line,
  `...GOOGLE_ADS_CUSTOMER_ID=7416088297` stuck directly onto the end of the
  token with no newline — split back into two proper lines.)

  With the new refresh token, confirmed via `ListAccessibleCustomers` +
  direct `SELECT customer.id, customer.test_account, customer.manager FROM
  customer` queries:
  - `GOOGLE_ADS_LOGIN_CUSTOMER_ID=1286821756` — "MMM Agents Testing Account",
    `test_account=True`, `manager=True`. The real test manager account.
  - `GOOGLE_ADS_CUSTOMER_ID=4411037941` — "MMM Test Client",
    `test_account=True`, `manager=False`. **This one is genuinely active and
    queryable right now** — confirmed live, not assumed.

  **Phase 4 is unblocked for real, verified live, as of this session** — and
  then actually exercised end-to-end. See the entry immediately below for the
  full outcome: both a real Search and a real Performance Max campaign now
  exist in this account, independently verified, not just "created without
  error."

- 2026-07-05 (same session, immediately after): **Phase 4 fully working end-to-end,
  verified live, both campaign types.** With `GOOGLE_ADS_MUTATE_ENABLED=true`
  (set only as a script-local env override, never written to the persistent
  `.env` — that stays `false` by default), ran
  `get_ads_client().create_paused_campaigns(...)` for real against `4411037941`.
  Took 5 rounds of real API errors to get right — exactly the kind of thing
  no amount of offline verification could have caught, and each one fixed in
  turn:
  1. `client.get_type("FieldMask")` doesn't exist (found earlier this
     session, structurally) — confirmed for real: fixed to
     `google.protobuf.field_mask_pb2.FieldMask`.
  2. `manual_cpc.enhanced_cpc_enabled` → `OPERATION_NOT_PERMITTED_FOR_CONTEXT`
     — Enhanced CPC appears restricted for new campaigns now. Fixed by
     activating the `manual_cpc` oneof via an empty message assignment
     (`campaign.manual_cpc = client.get_type("ManualCpc")` — note
     `get_type()` already returns an instance, not a class; no `()` needed)
     instead of setting that field.
  3. `contains_eu_political_advertising` — a genuinely **required** Campaign
     field in this API version (matches the same disclosure question seen in
     Google's own UI wizard earlier in this session). Added to both Search
     and PMax builders.
  4. `explicitly_shared` on CampaignBudget — new budgets default to
     shareable, which is incompatible with per-campaign bidding strategies
     (`BIDDING_STRATEGY_TYPE_INCOMPATIBLE_WITH_SHARED_BUDGET`). Fixed to
     `budget.explicitly_shared = False`.
  5. `DUPLICATE_CAMPAIGN_NAME` — the LLM-drafted campaign name has no
     uniqueness guarantee (unlike the deterministic demo planner's
     timestamp-suffixed names) and a same-named campaign already existed
     from an earlier failed attempt (Google doesn't roll back a campaign
     that already committed just because a *later* campaign in the same
     Python loop throws). Fixed with a new `unique_campaign_name()` helper in
     `google_ads_builders.py` that appends a timestamp at creation time,
     used by both builders — this is a builder-level guarantee now, not
     the planner's job.

  Performance Max needed substantially more iteration, all found live:
  6. `REQUIRED_BUSINESS_NAME_ASSET_NOT_LINKED` / `REQUIRED_LOGO_ASSET_NOT_LINKED`
     — this account has "Brand Guidelines" enabled, which requires a business
     name + logo linked as **CampaignAsset** (not just AssetGroupAsset)
     before the campaign can be created — and critically, linking them in a
     *separate, later* mutate call doesn't satisfy it, since it's validated
     atomically at campaign-creation time. Simplest fix: found and set
     `campaign.brand_guidelines_enabled = False` to opt out of the whole
     feature for these campaigns, rather than building the CampaignAsset
     linking (tried first, removed again once the simpler flag was found).
  7. `NOT_ENOUGH_HEADLINE_ASSET` / `..._DESCRIPTION_ASSET` / etc. — creating
     an empty AssetGroup and linking assets afterward *always* fails, even
     within one compound batch, because Google validates each operation
     against what precedes it in the *submission order* of the same batch,
     not the batch as a whole. Rewrote `create_pmax_campaign` to use
     `GoogleAdsService.mutate()` with temporary negative-numbered resource
     names (Google's own documented pattern for this), ordered strictly:
     campaign → all assets (including a business name text asset, a
     baseline PMax requirement independent of the Brand Guidelines flag,
     which the first version of this function had missed entirely) → asset
     group → asset-group-asset links, last.

  **Independently verified after the fact** (not just trusting the "success"
  message) by querying the account back: both campaigns exist, `PAUSED`,
  correct `advertising_channel_type`; the Search ad group has all 7 real
  keywords; the PMax asset group has exactly 10 linked assets (3 headlines +
  1 long headline + 2 descriptions + 1 business name + 3 placeholder
  images — matches exactly). Full test suite: **27/27 still passing**
  throughout every fix.

  Net effect: `ads_agent/google_ads_builders.py` and
  `ads_agent/google_ads_pmax_builders.py` are no longer "best-effort,
  unverified" — both campaign-creation paths are now confirmed working
  against a real (test) Google Ads account. `GOOGLE_ADS_MUTATE_ENABLED`
  remains `false` in `.env` and on Cloud Run by default; flip it locally
  (as a shell/script env override, not a permanent `.env` change) to exercise
  this again. Note: the test account now has a handful of paused test
  campaigns accumulated from this debugging process (harmless — test
  account, no spend, no real ads — but worth knowing they're there if
  Sameer looks at the account directly).

- 2026-07-05 (same day): **Extended the agentic layer to Meta (Facebook/Instagram)
  Ads — Phase 6, see `META_ADS_AGENT_PLAN.md`.** The MMM's `social` channel
  ($307,995/week recommended, +75% vs. current — the strongest growth signal of
  any channel) had never been wired into the agentic layer at all; only
  `search`/`display`/`digital_video` fed Google Ads. Built as a fully parallel
  track (`ads_agent/meta_schemas.py`, `meta_planner.py`, `meta_ads_client.py`,
  `meta_ads_builders.py`), mirroring the Google Ads Phase 1/4 pattern exactly,
  rather than touching the existing, already-verified-live Google Ads
  schemas/planner/client — kept those at zero risk. Also extracted the
  placeholder-image generator (previously private to
  `google_ads_pmax_builders.py`) into a shared `ads_agent/placeholder_images.py`,
  the one touch to existing Google Ads code (pure refactor, re-verified the
  existing test suite passed unchanged). Added a "Meta Ads (Phase 6,
  unverified)" section to `streamlit_app.py`. Sameer confirmed he has no Meta
  Business Manager / developer App / Ad Account / Page yet, so everything was
  built and tested in mock mode; the real-API builder is explicitly marked
  UNVERIFIED and will need a live debugging pass once those accounts exist —
  see `META_ADS_AGENT_PLAN.md`'s Phase 0 for the exact setup steps.

---

## Paste-ready custom instructions (for a claude.ai Project)

> I'm Sameer, a marketer (10 yrs ads experience) and MBA student building two portfolio
> projects: a Bayesian MMM in PyMC-Marketing 0.15.1 and a Google Ads agent. I don't code
> — write all code for me, heavily commented, with exact copy-paste commands. Teach with
> business stories and worked numeric examples BEFORE any formula or jargon. If I don't
> understand, change the explanation rather than repeating it. Challenge my assumptions
> politely. Refer to HANDOFF.md in my project files for full context and current status,
> and remind me to update its status log when we finish something.
