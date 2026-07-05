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
- [ ] Business Manager created
- [ ] A Facebook Page created, Page ID noted
- [ ] Ad Account created, Ad Account ID noted
- [ ] Developer App created, App ID + App Secret noted
- [ ] Long-lived access token generated with `ads_management` scope
- [ ] All five values added to `.env` (`META_ADS_APP_ID`, `META_ADS_APP_SECRET`,
      `META_ADS_ACCESS_TOKEN`, `META_ADS_AD_ACCOUNT_ID`, `META_ADS_PAGE_ID`)

None of this is done yet as of 2026-07-05 — Sameer confirmed no Business Manager, App,
or Ad Account exist. Everything below was built in mock mode and against Meta's
documented API shape, not yet run live.

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
