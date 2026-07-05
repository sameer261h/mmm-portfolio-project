# Marketing Mix Model + Agentic Ads System — Portfolio Project

**In one sentence:** a statistical model decides *how much* budget each marketing channel deserves, and an agentic system decides *what to actually do about it* — draft the campaigns, watch performance, propose changes — with a human approving every real action.

Two portfolio pieces in one repo, deliberately kept separate in framing:

1. **A Bayesian Marketing Mix Model** (classical statistics — PyMC-Marketing) that quantifies channel ROI and recommends a budget reallocation.
2. **An agentic system** built on top of it — campaign planning, a read-only analyst agent, an operator agent with human-approval-gated writes, and real Google Ads + Meta Ads API campaign creation.

**Honest framing (deliberate, not a hedge):** the MMM is classical statistics, not AI. The agentic AI is entirely in the layer built on top of it. Keeping this distinction clear is what makes the story credible in an interview rather than oversold — same reason the [Tools/Skills/Evals/Levels breakdown below](#tools--skills--evals--levels) names an honest gap instead of hiding it.

**Quick links for reviewers:** [Live demo](https://mmm-ads-agent-818953231119.us-central1.run.app) (no login) · [Track 1 notebooks](notebooks/) · [Track 2 code](ads_agent/) · [Full build log](HANDOFF.md)

---

## Track 1 — Bayesian Marketing Mix Model

**Resume bullet:**
> Built a Bayesian Marketing Mix Model (PyMC-Marketing) on 4 years of weekly retail data across 10 media channels; quantified channel ROI with uncertainty intervals and recommended a budget reallocation projected to lift revenue by X% at constant spend.

Real (anonymized) US retailer data, 200+ weeks (2014–2018), from [sibylhe/mmm_stan](https://github.com/sibylhe/mmm_stan). 10 spend channels grouped into 7 (`tv`, `social`, `audio`, `digital_video`, `display`, `search`, `print_mail`) — see `data/DATA_DICTIONARY.md`.

```
notebooks/01_data_exploration.ipynb   ← load, clean, understand the data
notebooks/02_build_mmm.ipynb          ← build, validate, and use the model
```

**Stack decision (know this for interviews):** chose **PyMC-Marketing** over Robyn (Meta) and Meridian (Google) because it's fully Bayesian (ROI estimates come with credible intervals — "Search ROI is 2.1x ± 0.4" — which is what budget decisions actually need), the model specification is transparent Python (every prior and transform is visible and defensible), and it's the most-downloaded open-source MMM library with strong docs. Robyn is ridge regression + evolutionary search — fast but harder to defend statistically. Meridian is strongest for geo-level data, which this dataset doesn't have.

---

## Track 2 — Agentic ads system (Google Ads + Meta Ads)

**Resume bullet:**
> Built an agentic ads analyst/operator on top with human-in-the-loop approval across Google Ads and Meta Ads, deployed on Cloud Run.

The MMM's recommended budget is the **strategic layer**; this agent is the **tactical layer** that turns it into actual Google Ads and Meta Ads actions — with a human approval gate before anything real happens.

| Phase | What it does | Status |
|---|---|---|
| 1 — Campaign planner | LLM drafts paused Search + PMax campaigns from the MMM's budget split | ✅ Live |
| 2 — Analyst agent | Answers questions ("why did CPA rise?") by autonomously deciding which read-only tool to call — zero write access | ✅ Live |
| 3 — Operator agent | Proposes budget/pause/negative-keyword changes as a structured ticket; **only applies after human approval** | ✅ Live |
| 4 — Real campaign creation | Actual Google Ads API calls (Search + Performance Max) against a real test account | ✅ Verified live |
| 6 — Meta Ads | Same planner → paused-campaign → approval-gate pattern, activating the MMM's `social` budget on Facebook/Instagram | 🟡 Built, mock-mode only — real API pending Meta account setup |

**What makes it agentic, specifically:** the analyst agent decides *which* of four tools to call based on the question, reads the results, and can call another tool based on what it learned before answering — a genuine reason → act → observe loop, not a single prompt-response call. The operator agent reasons over live account state to decide *what* action to propose and *which* campaign to target. Both feed into real, gated, real-world actions (Phase 4), not just generated text.

### Tools / Skills / Evals / Levels

Honest breakdown, not marketing — what each agent can actually do, named per [OpenAI's Skills/Evals framing](https://developers.openai.com/blog/eval-skills) and [Vellum's L0–L6 agentic-behavior levels](https://www.vellum.ai/blog/levels-of-agentic-behavior):

| | Planner (Phase 1/6) | Analyst (Phase 2) | Operator (Phase 3) |
|---|---|---|---|
| **Tools** | none — one structured-output call | `list_campaigns`, `get_performance`, `get_search_terms`, `get_budget_pacing` (read-only) | reads the same 4 tools, writes via `update_campaign_budget` / `pause_campaign` / `add_negative_keyword` (human-gated) |
| **Skill** | `SYSTEM_PROMPT` in `planner.py` / `meta_planner.py`: draft a paused campaign from a budget envelope | `SYSTEM_PROMPT` in `analyst_agent.py`: answer performance questions using only read tools | `SYSTEM_PROMPT` in `operator_agent.py`: propose one change as a `ChangeTicket`, never apply it |
| **Level** | **L1** — single prompt → structured response, no tool loop, no state | **L2** — the model decides which tool(s) to call and can chain a second call on what it learns | **L3** — observes account state, plans a proposal, but a human approves before anything real happens |

**Evals — the honest gap:** the 37 pytest tests check *code correctness* (schema validation, guardrail math, mock writes) — they are not evals. There is currently no harness that runs a fixed set of representative requests through the analyst/operator and scores whether the *tool choice or proposed action was actually good*, only whether the code executed without crashing. Flagged here deliberately rather than glossed over — a real next step, not a solved problem.

**Safety design:**
- Every write path enforces hard guardrails in code (budget caps, daily rate limit, action allowlist) — not just prompt instructions
- Nothing is ever auto-enabled; campaigns are always created `PAUSED`
- Defaults to mock mode (`GOOGLE_ADS_MUTATE_ENABLED=false`, `META_ADS_MUTATE_ENABLED=false`) everywhere, including the public demo — the real API path is a deliberate, explicit opt-in

```
ads_agent/
├── planner.py                — Phase 1: campaign plan generation
├── analyst_data.py / analyst_tools.py / analyst_agent.py   — Phase 2
├── operator_state.py / operator_agent.py                   — Phase 3
├── guardrails.py              — hard safety checks, independent of the LLM
├── google_ads_client.py       — Mock (default) / Real client switch
├── google_ads_builders.py / google_ads_pmax_builders.py    — Phase 4: real API calls
├── placeholder_images.py      — shared placeholder-image generator (Google PMax + Meta)
└── meta_schemas.py / meta_planner.py / meta_ads_client.py / meta_ads_builders.py
                                — Phase 6: same pattern, extended to Meta (Facebook/Instagram) Ads
streamlit_app.py               — the UI tying all phases together
```

Full build history, every real bug found via live testing, and current status: see `HANDOFF.md`, `GOOGLE_ADS_AGENT_PLAN.md`, and `META_ADS_AGENT_PLAN.md`.

---

## Project structure

```
mmm-portfolio-project/
├── README.md                  ← you are here
├── LICENSE                    ← MIT
├── HANDOFF.md                 ← full session-by-session build log (read this for current status)
├── GOOGLE_ADS_AGENT_PLAN.md   ← Track 2 phase-by-phase plan + status
├── META_ADS_AGENT_PLAN.md     ← Track 2 Phase 6 (Meta Ads) plan + status
├── requirements.txt / requirements-cloudrun.txt
├── Dockerfile                 ← Cloud Run deployment
├── streamlit_app.py           ← Track 2 UI
├── ads_agent/                 ← Track 2 package (see above)
├── tests/                     ← pytest suite for ads_agent/
├── data/
│   └── DATA_DICTIONARY.md
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   └── 02_build_mmm.ipynb
└── docs/                      ← supplementary reading, kept out of the root on purpose
    ├── LEARNING_GUIDE.md      ← MMM concepts + interview prep
    ├── DESIGN_DOCUMENTATION.md
    └── MMM_Project_Guide.pdf / MMM_Study_Guide.html
```

## Setup (one time, ~15 min)

1. Install Python via [Miniconda](https://docs.anaconda.com/miniconda/) (recommended — handles PyMC's dependencies cleanly).
2. Open a terminal (macOS: Terminal app) and run:

```bash
cd ~/Downloads/mmm-portfolio-project
conda create -n mmm python=3.11 -y
conda activate mmm
pip install -r requirements.txt
```

3. **Track 1**: `jupyter lab` → open `notebooks/01_data_exploration.ipynb`, run cells top-to-bottom with Shift+Enter.
4. **Track 2**: `streamlit run streamlit_app.py` (runs in mock mode with no credentials needed; add an `OPENAI_API_KEY` to `.env` — copy from `.env.example` — for real LLM-generated plans instead of the deterministic demo fallback). Run tests with `pytest tests/ -v`.

## The dataset

Real (anonymized) US retailer data, 200+ weeks (2014–2018), from the well-known
[sibylhe/mmm_stan](https://github.com/sibylhe/mmm_stan) repository (originally a Kaggle dataset).
Notebook 01 downloads it automatically. See `data/DATA_DICTIONARY.md`.
