# AGENTS.md

Codex: read this file, then HANDOFF.md in this same folder, before doing anything.
HANDOFF.md is the source of truth for project status — this file is the source of
truth for HOW to work with Sameer.

## Who you're working with

Sameer — marketer (10 yrs ads experience), MBA student (IPMX), building this as a
placement/portfolio project. He does NOT code. Python is rusty/minimal.

## How to work with him

- Write ALL code for him, heavily commented, with exact copy-paste terminal commands.
  Never assume he can debug an error alone — walk him through what it means and what
  to run next.
- Teach with a business story and a worked numeric example BEFORE any formula or
  jargon. If he says he's not following, change the explanation — don't just repeat
  the same one slower.
- Challenge his assumptions politely. He wants a sparring partner, not a yes-man.
- He goes into extended flow states — give him meaty, sequential, step-by-step
  tracks rather than one tiny step at a time.
- When something meaningful finishes, remind him to update HANDOFF.md's status log
  (or offer to do it yourself and have him confirm).

## Current known state (verify against HANDOFF.md — it's updated more often than this file)

- requirements.txt pins `pymc==5.23.0` alongside `pymc-marketing==0.15.1` on purpose.
  Without that pin, pip installs the newest pymc, which breaks notebook 02's budget
  optimizer with `ImportError: cannot import name 'rvs_in_graph'`. Don't "helpfully"
  remove or bump this pin without re-testing the optimizer import.
- notebook 01 (`notebooks/01_data_exploration.ipynb`) runs clean end-to-end — verified
  2026-07-03. `data/raw_data.csv` and `data/model_data.csv` already exist from that run.
- notebook 02's budget-optimizer cell was patched so it correctly unpacks
  `allocation, opt_result = mmm.optimize_budget(...)` (it returns a tuple, not a
  single object).
- notebook 02 cell 5 (`mmm.fit(...)`) is a 10-40 minute MCMC sampling step. That's
  normal — not a bug, not a hang. Don't "fix" it by reducing chains/draws without
  telling Sameer, since that changes the statistical validity of the result.

## Environment

- Local Python env: conda env named `mmm`, Python 3.11.
  Activate with `conda activate mmm` before running anything in this repo.
- Install/refresh deps with `pip install -r requirements.txt` from the repo root.

## Two tracks in this one repo

1. Bayesian MMM (primary) — `notebooks/01_data_exploration.ipynb` then
   `notebooks/02_build_mmm.ipynb`. Full detail in README.md and docs/LEARNING_GUIDE.md.
2. Google Ads agent (secondary) — plan in `GOOGLE_ADS_AGENT_PLAN.md`. Not started yet
   as of 2026-07-03; check its own status log before assuming any phase is done.
