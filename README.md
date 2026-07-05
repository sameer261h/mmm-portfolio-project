# Marketing Mix Model (MMM) — Portfolio Project

**Goal:** Build a Bayesian Marketing Mix Model on real retailer data using PyMC-Marketing, quantify each channel's ROI, and recommend an optimal budget reallocation.

**Resume bullet (target):**
> Built a Bayesian Marketing Mix Model (PyMC-Marketing) on 4 years of weekly retail data across 10 media channels; quantified channel ROI with uncertainty intervals and recommended a budget reallocation projected to lift revenue by X% at constant spend.

---

## Project structure

```
mmm-portfolio-project/
├── README.md              ← you are here (roadmap + setup)
├── LEARNING_GUIDE.md      ← MMM concepts + interview prep
├── requirements.txt
├── data/
│   └── DATA_DICTIONARY.md ← what every column means
└── notebooks/
    ├── 01_data_exploration.ipynb   ← load, clean, understand the data
    └── 02_build_mmm.ipynb          ← build, validate, and use the model
```

## Setup (one time, ~15 min)

1. Install Python via [Miniconda](https://docs.anaconda.com/miniconda/) (recommended — handles PyMC's dependencies cleanly).
2. Open a terminal (macOS: Terminal app) and run:

```bash
cd ~/Downloads/mmm-portfolio-project
conda create -n mmm python=3.11 -y
conda activate mmm
pip install -r requirements.txt
jupyter lab
```

3. Jupyter opens in your browser. Open `notebooks/01_data_exploration.ipynb` and run cells top-to-bottom with Shift+Enter.

## Roadmap (4 weeks, ~5–8 hrs/week)

| Week | Milestone | Output |
|---|---|---|
| 1 | Read LEARNING_GUIDE.md; run notebook 01; understand every column | Clean modeling dataset |
| 2 | Run notebook 02 through model fitting; understand adstock/saturation/priors | Fitted model + diagnostics |
| 3 | ROI analysis, saturation curves, budget optimizer | Channel ROI table + reallocation recommendation |
| 4 | Write it up: 1-page case study + README polish; push to GitHub | Portfolio piece + interview story |

## The dataset

Real (anonymized) US retailer data, 200+ weeks (2014–2018), from the well-known
[sibylhe/mmm_stan](https://github.com/sibylhe/mmm_stan) repository (originally a Kaggle dataset).
Notebook 01 downloads it automatically. See `data/DATA_DICTIONARY.md`.

## Stack decision (know this for interviews)

Chose **PyMC-Marketing** over Robyn (Meta) and Meridian (Google) because:
- Fully Bayesian → ROI estimates come with credible intervals ("Search ROI is 2.1x ± 0.4"), which is what budget decisions need.
- Python, transparent model specification — every prior and transform is visible and defensible.
- Most-downloaded open-source MMM library; excellent docs.
- Robyn = ridge regression + evolutionary hyperparameter search (fast but harder to defend statistically). Meridian = strongest for geo-level data, which this dataset doesn't have.
