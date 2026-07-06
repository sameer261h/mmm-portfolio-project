# Meta Ads Agent — Build Plan (Phase 6 of the agentic system)

Companion to `GOOGLE_ADS_AGENT_PLAN.md`. Extends the same MMM → agent → human-approval
pattern to a second platform: Meta (Facebook/Instagram) Ads, activating the MMM's
`social` channel recommendation that the Google Ads flow never touches.

**Architecture in one line:** MMM (strategic: channel budgets, `social` = $307,995/week
recommended, +75% vs. current) → Meta planner agent (tactical: one paused Feed campaign)
→ Meta Marketing API, with the same human approval gate on every write as Google Ads.

**Why this exists:** `ads_agent/budget.py`'s `MMM_RECOMMENDED_WEEKLY` dict only ever fed
`search`/`display`/`digital_video` into Google Ads. `social` — the MMM's single
highest-percentage-growth recommendation of any channel — had a real, model-backed
dollar figure with nowhere to go. This phase gives it one.

---

## Phase 0 — Meta access setup (Sameer to do — no free test account exists here)

Unlike Google Ads, Meta has **no risk-free sandbox account**. The safety model in this
codebase is structural instead: campaigns/ad sets/ads are always created `PAUSED`,
`enable_campaigns()` always raises `NotImplementedError`, and nothing here ever touches
billing. Still, real API calls need a real Business Manager, App, Ad Account, and Page.

### Step 1 — Meta Business Manager (~10 min)
1. Go to https://business.facebook.com → create a Business Manager (any name is fine).
2. This is the umbrella account everything else (Ad Account, Page, App access) hangs off.

### Step 2 — A Facebook Page (~5 min)
1. Meta ads are inherently posted "as" a Page — there is no way around this in their
   model (unlike Google, where the landing page URL is enough).
2. Create a Page under the Business Manager (any name/category — e.g. "Anonymized
   Retailer Demo"). Note its numeric Page ID.

### Step 3 — Ad Account (~5 min)
1. In Business Manager → Accounts → Ad Accounts → create one. No payment method needs
   to be attached to build and test paused campaigns.
2. Note its numeric Ad Account ID (without the `act_` prefix — the code adds that).

### Step 4 — Developer App + access token (~15 min + possible review wait)
1. Go to https://developers.facebook.com/apps → create an App → add the "Marketing API"
   product.
2. Generate a long-lived access token scoped to `ads_management` for your Ad Account
   (via the Graph API Explorer or a System User token in Business Manager — a System
   User token is preferable since it doesn't expire on a normal login cycle).
3. Note the App ID, App Secret, and the access token.
4. Some permissions may require Meta's App Review before working outside your own
   Business Manager's test users — for paused-only campaign creation on your own ad
   account, this is typically not required, but budget time for it if Meta asks.

### Phase 0 done when you have:
- [x] Business Manager created
- [x] A Facebook Page created, Page ID noted
- [x] Ad Account created, Ad Account ID noted
- [x] Developer App created, App ID + App Secret noted
- [x] Long-lived access token generated with `ads_management` scope (System User token)
- [x] All five values added to `.env` (`META_ADS_APP_ID`, `META_ADS_APP_SECRET`,
      `META_ADS_ACCESS_TOKEN`, `META_ADS_AD_ACCOUNT_ID`, `META_ADS_PAGE_ID`)

**Phase 0 complete as of 2026-07-06** — see status log below for the live verification.

**Update 2026-07-06: Phase 0 is now complete** (Business Portfolio, Page, Ad Account,
Developer App, System User access token — all created and live-verified, see status log
below). Everything below was originally built in mock mode against Meta's documented API
shape; the real-API builder (`meta_ads_builders.py`) is next in line for the same kind
of live debugging pass Google Ads Phase 4 needed.

---

## Phase 6 — Meta Ads planner + builder (mirrors Google Ads Phases 1 + 4)

**Built (2026-07-05), mock-mode complete, real-API path UNVERIFIED** (blocked on Phase 0
above, not on anything in this codebase):

- `ads_agent/budget.py` — `calculate_meta_ads_split()` and
  `MMM_RECOMMENDED_WEEKLY_META = {"social": 307_995.0}`, pulled from the same
  notebook 02 optimizer output as the existing Google Ads numbers (confirmed directly
  from the notebook's saved cell output, not invented).
- `ads_agent/meta_schemas.py` — `MetaCampaignPlan`/`MetaCampaignDraft`/
  `MetaAdCreativeDraft`/`MetaCampaignObjective`, mirroring `schemas.py`'s shape for
  Meta's Campaign → Ad Set → Ad structure. Kept fully separate from `CampaignPlan` so
  the already-verified-live Google Ads schemas and validators are never touched.
- `ads_agent/meta_planner.py` — `generate_meta_campaign_plan()`: OpenAI Responses API
  path (same `to_openai_strict_schema()` helper as `planner.py`) with a deterministic
  demo-mode fallback. v1 drafts exactly one paused Feed campaign (not a Search/PMax-style
  pair — Meta's ad taxonomy doesn't map onto that split).
- `ads_agent/guardrails.py` — added `validate_meta_plan_for_paused_creation()` and
  `validate_meta_enable_request()`, mirroring the Google Ads guardrail checks (budget
  caps, PAUSED-only, no delete-style names) for the Meta-shaped plan.
- `ads_agent/meta_ads_client.py` — `MockMetaAdsClient` / `RealMetaAdsClient` /
  `get_meta_ads_client()`, mirroring `google_ads_client.py`'s Mock/Real split exactly,
  gated by `META_ADS_MUTATE_ENABLED` (default `false`). `enable_campaigns()` always
  raises `NotImplementedError`, same as Google's client — enabling is out of scope
  until reviewed with Sameer.
- `ads_agent/meta_ads_builders.py` — `create_meta_campaign_from_draft()` using the
  `facebook-business` SDK: Campaign (`special_ad_categories=[]`, paused) → Ad Set
  (budget in cents, targeting, paused) → Ad Creative (placeholder image + Page-attributed
  copy) → Ad (paused). **UNVERIFIED** — written from Meta's documented API shape, not
  run against a live account. Expect a real debugging pass once Phase 0 is done, the
  same way Google Ads Phase 4 needed 7 rounds of real fixes before being confirmed.
- `ads_agent/placeholder_images.py` — extracted from
  `ads_agent/google_ads_pmax_builders.py` (was `_generate_placeholder_image`, Google
  Ads-only) into a shared module used by both the PMax and Meta builders. Pure
  refactor, no behavior change — re-verified the existing Google Ads test suite passed
  unchanged afterward.
- Streamlit "Meta Ads (Phase 6, unverified)" section — its own Generate Plan /
  Create Paused Campaigns / Enable buttons, mirroring the existing Google Ads plan
  section, using a separate `meta_plan_json` session-state key so it doesn't interfere
  with the Google Ads plan already on screen.
- `tests/test_meta_ads.py` — schema validation (including `extra="forbid"` strict-mode
  shape), `calculate_meta_ads_split()` math against the real $307,995 figure,
  `MockMetaAdsClient` write methods, and the deterministic demo-mode planner fallback.

**Known simplifications** (documented in code, not silently guessed at):
- `interests` targeting is illustrative text only, not resolved to real Meta interest
  IDs (needs a Targeting Search API lookup not built in this pass).
- Geo targeting uses a small hardcoded country-name → ISO-code map (same scoping
  decision as Google builder's language-constant map), defaulting to `US` for anything
  unrecognized.
- Uses one placeholder image (PIL-generated, shared with the Google PMax builder) as
  the ad creative's image asset — no real creative exists for this project.

**Out of scope for this phase** (flagged, not dropped): extending the Phase 2 analyst
or Phase 3 operator agents to reason about Meta campaigns. `get_search_terms()` is
inherently a Google Search concept with no Meta equivalent; worth a follow-up phase once
Meta campaigns are live and there's real performance data to ask questions about.

## Status log
- 2026-07-05: Plan created and Phase 6 built end-to-end in mock mode (schemas, budget
  split using the real MMM `social` figure, planner, guardrails, mock/real client,
  real-API builder, Streamlit UI, tests). Sameer confirmed no Meta Business Manager /
  App / Ad Account / Page exist yet — Phase 0 above is the next step before any of the
  real-API code can be live-verified.
- 2026-07-06: **Phase 0 completed.** Created a Business Portfolio, a Facebook Page
  ("Retail Company"), a Meta developer app (Marketing API use case), and an Ad Account —
  hit one real snag along the way: the first Business Portfolio got a "Business is not
  allowed to claim App" restriction (Meta's abuse-detection flagging a new
  business/account combo), resolved by Sameer outside this session (app creation
  succeeded on retry). Also had to create a second Ad Account after the first attempt,
  now `act_1419013410289450`. Generated a long-lived System User access token (Business
  Settings → Users → System users → Add Assets → Generate New Token, scoped to
  `ads_management`) rather than a short-lived Graph API Explorer token, matching the
  plan's stated preference. All five values
  (`META_ADS_APP_ID`/`META_ADS_APP_SECRET`/`META_ADS_PAGE_ID`/`META_ADS_AD_ACCOUNT_ID`/
  `META_ADS_ACCESS_TOKEN`) written to `.env`, confirmed set via length-only checks (no
  secret values ever printed to chat). **Live-verified**, not just assumed: a real
  `GET /act_1419013410289450?fields=name,account_status,currency` Graph API call
  returned actual account data (name "Agents Testing", `account_status: 1` = active,
  currency USD) — the token and ad account access genuinely work.

  Also fixed an unrelated `.env` corruption found while verifying (same class of bug
  HANDOFF.md already logged once before): `GOOGLE_ADS_REFRESH_TOKEN` and
  `GOOGLE_ADS_CUSTOMER_ID` had been pasted onto one line with no newline between them,
  silently dropping the `GOOGLE_ADS_CUSTOMER_ID` line entirely. Split back into two
  lines; confirmed with Sameer that the customer/login IDs themselves
  (`2676053905`/`7416088297`) are current, live test accounts, not stale ones — only the
  formatting was broken, no values were changed.

  **Not done yet:** `meta_ads_builders.py` (the real-API campaign creation code) is
  still unverified against this live account — that's the next step, and per the
  Google Ads Phase 4 precedent, expect a real debugging pass once we actually try it.

- 2026-07-06 (same day): **Live debugging pass on `meta_ads_builders.py`, same pattern
  as Google Ads Phase 4.** Ran `get_meta_ads_client().create_paused_campaigns(...)` for
  real against `act_1419013410289450` with `META_ADS_MUTATE_ENABLED=true` set as a
  process-local override only (never written to `.env`, which stays `false`). Found and
  fixed 3 real code bugs plus 2 real `.env`/account-config bugs before hitting a genuine
  external blocker.

  **Code fixes in `ads_agent/meta_ads_builders.py`** (all confirmed necessary by real
  API responses, not guessed):
  1. Campaign creation needs `is_adset_budget_sharing_enabled: False` explicitly — Meta
     now requires this whenever budget lives on the ad set rather than the campaign
     (`error_subcode 4834011`).
  2. Ad set creation needs an explicit `bid_strategy` — added
     `AdSet.BidStrategy.lowest_cost_without_cap` (auto-bid, no manual cap) since none of
     this project's plans specify a bid amount (`error_subcode 2490487`).
  3. Ad set targeting needs `targeting_automation: {"advantage_audience": 0}` — newly
     required by Meta; set to `0` (off) since this project's age/geo targeting is
     deliberate and shouldn't be silently widened by Meta's Advantage+ audience
     expansion (`error_subcode 1870227`).

  **Config fixes, found only by testing live (not visible from reading code):**
  4. `.env`'s `META_ADS_PAGE_ID` was simply wrong — `61591503430268` instead of the
     Business's actual owned Page ID `1182521951615637` ("Retail Company"). Confirmed
     via `GET /{business_id}/owned_pages`. Also fixed a stray typo in
     `META_ADS_APP_ID` (trailing `c`: `1033242915760732c` → `1033242915760732`) found
     while cross-checking against the `/debug_token` response — it hadn't broken
     anything yet since app_id isn't strictly validated on every call, but was wrong.
  5. The System User had `ads_management`/`pages_manage_ads` *scopes* on its token but
     had never actually been assigned the Page as an asset in Business Settings
     (`/me/accounts` returned empty) — fixed by Sameer via Business Settings → Users →
     System Users → Add Assets → Pages → "Retail Company" → Full Control. Separately,
     the Meta developer app itself was still in Development Mode, which blocks ad
     creatives from referencing a real Page (`error_subcode 1885183`) — fixed by
     publishing the app to Live mode (required Privacy Policy URL + icon + category
     under App Settings → Basic first).

  With all 5 of the above fixed, live-verified in order: **Campaign → Ad Set → Ad
  Creative all created successfully** against the real account (paused, confirmed via
  the account's `/campaigns` edge — 8 real campaign objects exist from the debugging
  iterations, left in place since delete requires a permission this System User's ad
  account role doesn't grant; harmless, paused, no spend, no audience ever served).

  **Genuine external blocker on the final step (creating the `Ad` object itself):**
  Meta requires a payment method on file before it will create an `Ad` object, even one
  that stays `PAUSED` forever (Campaigns/Ad Sets/Creatives do not have this requirement
  — only discovered by hitting it live: `error_subcode 1359188`, "No payment method").
  This contradicts what Phase 0 above assumed ("No payment method needs to be attached
  to build and test paused campaigns") — that's only true for 3 of the 4 objects.
  Sameer's ad account is USD-denominated but his available cards are Indian
  (INR-issued) without international/forex transactions enabled — a well-known Meta
  Ads pain point for India-based advertisers, not fixable in code. Adding a payment
  method is also currently blocked at the Business level (Ad Accounts section
  greyed out — likely a new/unverified-Business limit on how many ad accounts or
  billing profiles can be created), so a second ad account with different
  region/currency isn't a quick workaround either.

  **Final status, accepted as done for this project:** 3 of 4 Meta object types
  (Campaign, Ad Set, Ad Creative) are live-verified working. The 4th (`Ad`) is
  code-complete and believed correct (same construction pattern as the other 3, all of
  which needed and got real fixes) but blocked from live verification by an external
  billing/region constraint outside this codebase's control. Rebuilding the entire
  Meta identity stack (new email, Facebook account, Page, Business, App, tokens) was
  considered and rejected — the blocker is tied to Sameer's India-based
  identity/billing profile, not this specific account, so a fresh Business Portfolio
  would very likely hit the same wall. Full test suite: 37/37 passing throughout.
