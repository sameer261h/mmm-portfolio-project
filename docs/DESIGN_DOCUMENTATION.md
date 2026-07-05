# Design Documentation — MMM-Driven Google Ads Campaign Agent

**Applicant:** Sameer
**Tool name:** MMM Google Ads Agent (working title)
**Purpose of this document:** Submitted as part of a Google Ads API Basic access
application, describing what the tool is, how it uses the API, who it serves, and the
safeguards in place around automated actions.

---

## 1. Summary

This is a personal portfolio/research project connecting a statistical marketing model
(a Bayesian Marketing Mix Model, built with PyMC-Marketing) to Google Ads campaign
management. The MMM analyzes historical spend and revenue data to recommend how a
media budget should be split across channels (TV, social, search, display, video,
audio, print/mail). This tool takes the portion of that recommendation that is
executable in Google Ads (search, display, video/Performance Max) and turns it into
concrete campaign drafts — which a human then reviews and approves before anything is
created or enabled.

The intent is a **strategic-to-tactical pipeline**: MMM sets a budget envelope →
this tool proposes the Google Ads campaigns to spend that budget on → the account
owner approves every write.

## 2. Intended use and account scope

- **Who uses it:** the applicant only, managing their own Google Ads account(s) —
  personal/demo account plus Google Ads API test accounts used for development.
  This is **not** a tool for managing third-party or client accounts.
- **Why the API is needed:** to read account/campaign state and (once approved) create
  or modify campaigns programmatically, rather than manually through the UI, so the
  MMM's recommendations can be tested and iterated on as part of a portfolio project
  demonstrating applied marketing analytics + responsible automation design.
- **Expected volume:** low. This is a single-account personal project, not a
  multi-tenant or high-frequency system. Typical usage is a handful of read/write
  calls per session during development and demos, not continuous polling.

## 3. Architecture

```
Historical spend/revenue data
        │
        ▼
Bayesian MMM (PyMC-Marketing)  ──► channel-level budget recommendation
        │
        ▼
Budget translator (ads_agent/budget.py)
  – takes the Google-executable slice of the MMM recommendation
    (search + display + digital video)
  – converts it into a daily Search/Performance-Max split
        │
        ▼
Campaign planner (ads_agent/planner.py)
  – drafts one Search campaign + one Performance Max campaign
  – keywords, ad copy, PMax assets, rationale, risk flags
  – campaigns are always drafted as PAUSED
        │
        ▼
Guardrails (ads_agent/guardrails.py)
  – hard-coded checks independent of any LLM: budget caps, PAUSED-only creation,
    required PMax assets present, no delete-style actions
        │
        ▼
Human review (Streamlit UI)
  – the account owner edits/approves the plan before anything is sent to the API
        │
        ▼
Google Ads API client (ads_agent/google_ads_client.py)
  – executes only what was approved, and only as PAUSED campaigns
  – every action is written to an append-only audit log
```

## 4. Current implementation status (as of this document)

- **Built and working today (mock mode):** the full pipeline above runs end-to-end
  against a mock Google Ads client that logs intended API operations to a local audit
  file instead of calling the real API. This lets the planning, guardrail, and
  approval logic be fully tested before any real API credentials are used.
- **Gated behind explicit implementation + a manual flag:** the real API client
  (`RealGoogleAdsClient`) is present in the codebase as a scaffold but its write
  methods are intentionally unimplemented until (a) API access is granted and
  (b) the developer has explicitly enabled a `GOOGLE_ADS_MUTATE_ENABLED` environment
  flag. There is no path in the code today that reaches the live API.
- **Planned next (subject to this access review):** implement real, read-only account
  and performance queries first (list campaigns, get performance metrics, get search
  terms, get budget pacing) — zero mutation risk — followed by gated write operations
  (create paused campaigns, update budget, pause a campaign, add negative keywords),
  each requiring the same human-approval step already built into the UI.

## 5. Google Ads API usage

Planned API surface, in rollout order:

1. **Read-only reporting** (`GoogleAdsService.search` / `searchStream`): campaign
   list, cost/conversion metrics by date range, search terms report, budget pacing.
2. **Campaign creation** (`CampaignService`, `CampaignBudgetService`,
   `AdGroupService`, `AdGroupAdService`, `AssetService` for Performance Max assets):
   creating new Search and Performance Max campaigns, always in `PAUSED` status.
3. **Campaign management** (later phase): budget updates, pausing/enabling
   campaigns, adding negative keywords — each individually approval-gated, never
   batch-applied without review.

No use of billing/payment endpoints, no account-linking/invitation endpoints, and no
endpoints for managing other advertisers' accounts are planned.

## 6. Human-in-the-loop safeguards

This is the core design principle of the tool, not an afterthought:

- **Every campaign is created `PAUSED`.** Nothing serves impressions or spends money
  as a direct result of an automated action.
- **A separate, explicit "enable" step** is required after creation — creation and
  activation are two different human-approved actions, never combined.
- **Hard-coded guardrails independent of the LLM** (`guardrails.py`) reject any plan
  that: exceeds a configured daily budget cap, is not in `PAUSED` status at creation,
  is missing required creative assets, or contains delete-style operations. These
  checks run in code, not as prompt instructions, so they can't be bypassed by a
  model's output.
- **Full audit logging** — every generated plan and every mock/real action is
  appended to a local, timestamped audit log.
- **Kill switch** — a single environment variable (`GOOGLE_ADS_MUTATE_ENABLED`)
  gates whether the real API client can be used at all; default is off.
- **Planned rate limiting and dry-run mode** for the write-enabled phase (capping
  changes per day, and allowing every action to run as a no-op preview first).

## 7. Data handling and security

- Credentials (developer token, OAuth client secret, refresh token) are stored only
  in a local, gitignored `.env` file — never committed to source control, never
  hardcoded in source files.
- No customer PII is processed; the tool operates on aggregate spend/performance
  data and campaign configuration, not end-user data.
- All development and testing happens against Google Ads **test accounts**, which
  do not serve real ads or spend real money, before any real account is touched.

## 8. Compliance

The tool is designed to comply with the Google Ads API Terms of Service and required
minimum functionality expectations: it does not attempt to circumvent Google Ads
policy review, does not automate policy-violating content, does not manage
third-party accounts without their own authorization, and does not remove the human
approval step for any action that creates or changes live campaigns.
