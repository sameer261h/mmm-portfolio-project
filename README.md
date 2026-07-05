# Marketing Mix Model + Agentic Google Ads System — Portfolio Project

Two portfolio pieces in one repo, deliberately kept separate in framing:

1. **A Bayesian Marketing Mix Model** (classical statistics — PyMC-Marketing) that quantifies channel ROI and recommends a budget reallocation.
2. **An agentic Google Ads system** built on top of it — campaign planning, a read-only analyst agent, an operator agent with human-approval-gated writes, and real Google Ads API campaign creation.

**Honest framing (deliberate, not a hedge):** the MMM is classical statistics, not AI. The agentic AI is entirely in the Google Ads layer. Keeping this distinction clear is what makes the story credible in an interview rather than oversold.

**Live demo:** https://mmm-ads-agent-818953231119.us-central1.run.app (public, no login — click "Generate plan" or ask the analyst a question)

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

## Track 2 — Agentic Google Ads system

**Resume bullet:**
> Built an agentic Google Ads analyst/operator on top with human-in-the-loop approval, deployed on Cloud Run.

The MMM's recommended budget is the **strategic layer**; this agent is the **tactical layer** that turns it into actual Google Ads actions — with a human approval gate before anything real happens.

| Phase | What it does | Status |
|---|---|---|
| 1 — Campaign planner | LLM drafts paused Search + PMax campaigns from the MMM's budget split | ✅ Live |
| 2 — Analyst agent | Answers questions ("why did CPA rise?") by autonomously deciding which read-only tool to call — zero write access | ✅ Live |
| 3 — Operator agent | Proposes budget/pause/negative-keyword changes as a structured ticket; **only applies after human approval** | ✅ Live |
| 4 — Real campaign creation | Actual Google Ads API calls (Search + Performance Max) against a real test account | ✅ Verified live |

**What makes it agentic, specifically:** the analyst agent decides *which* of four tools to call based on the question, reads the results, and can call another tool based on what it learned before answering — a genuine reason → act → observe loop, not a single prompt-response call. The operator agent reasons over live account state to decide *what* action to propose and *which* campaign to target. Both feed into real, gated, real-world actions (Phase 4), not just generated text.

**Safety design:**
- Every write path enforces hard guardrails in code (budget caps, daily rate limit, action allowlist) — not just prompt instructions
- Nothing is ever auto-enabled; campaigns are always created `PAUSED`
- Defaults to mock mode (`GOOGLE_ADS_MUTATE_ENABLED=false`) everywhere, including the public demo — the real API path is a deliberate, explicit opt-in

```
ads_agent/
├── planner.py                — Phase 1: campaign plan generation
├── analyst_data.py / analyst_tools.py / analyst_agent.py   — Phase 2
├── operator_state.py / operator_agent.py                   — Phase 3
├── guardrails.py              — hard safety checks, independent of the LLM
├── google_ads_client.py       — Mock (default) / Real client switch
└── google_ads_builders.py / google_ads_pmax_builders.py    — Phase 4: real API calls
streamlit_app.py               — the UI tying all four phases together
```

Full build history, every real bug found via live testing, and current status: see `HANDOFF.md` and `GOOGLE_ADS_AGENT_PLAN.md`.

---

## Project structure

```
mmm-portfolio-project/
├── README.md                  ← you are here
├── HANDOFF.md                 ← full session-by-session build log (read this for current status)
├── GOOGLE_ADS_AGENT_PLAN.md   ← Track 2 phase-by-phase plan + status
├── LEARNING_GUIDE.md          ← MMM concepts + interview prep
├── requirements.txt / requirements-cloudrun.txt
├── Dockerfile                 ← Cloud Run deployment
├── streamlit_app.py           ← Track 2 UI
├── ads_agent/                 ← Track 2 package (see above)
├── tests/                     ← pytest suite for ads_agent/
├── data/
│   └── DATA_DICTIONARY.md
└── notebooks/
    ├── 01_data_exploration.ipynb
    └── 02_build_mmm.ipynb
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
