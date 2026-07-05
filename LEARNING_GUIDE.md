# MMM Learning Guide

Read this before touching the notebooks. ~30 minutes.

## 1. The business problem

A CMO spends across TV, search, social, radio, print. Sales happen. The question MMM answers:
**how much of each week's sales did each channel cause, and where should the next dollar go?**

Why not just track clicks (attribution)? Because attribution only sees digital, breaks with
privacy changes (iOS14, cookie deprecation), and can't measure TV/radio/print. MMM works on
aggregate data — no user tracking — which is why demand for MMM skills has surged since 2021.

## 2. The core model

At its heart, MMM is a regression on weekly data:

```
sales_t = baseline + Σ_channels β_c · f(spend_c,t) + Σ γ · controls_t + error
```

- **baseline** — sales you'd get with zero advertising (brand strength, distribution, habit)
- **controls** — price, promotions, holidays, seasonality, macro factors
- **f( )** — the two transforms below. This is what makes it MMM and not just regression.

### Transform 1: Adstock (carryover) — ads have an afterglow

**Story:** you run a pizza shop and spend ₹10,000 on a TV ad on Monday. Some people order
that evening. Ramesh sees it Monday but orders Friday. Priya orders two weeks later when
friends visit. The ad sits in people's heads and keeps nudging them — that is "carryover":
the effect *carries over* into future weeks. "Adstock" = the leftover stock of influence
the ad still has.

If the model only compared this week's spend to this week's sales, Ramesh's and Priya's
orders would look like they came from nowhere and TV would get too little credit. So we
replace "spend this week" with "advertising pressure in the air this week":

```
pressure_t = fresh spend_t + α · pressure_{t-1}        (0 < α < 1)
```

Worked example with α = 0.5 (memory halves each week): spend ₹10,000 once → pressure is
10,000 / 5,000 / 2,500 / 1,250 over weeks 1–4.

α is a **memory dial**. Search ads: α ≈ 0 (someone searching "pizza near me" buys *now*).
TV brand ads: α ≈ 0.6–0.8 (afterglow lasts weeks). The model learns each channel's dial
from the data.

### Transform 2: Saturation (diminishing returns) — the millionth rupee works less hard

**Story:** your town has 50,000 people. The first ₹1 lakh of ads reaches people who've
never heard of you — lots of new customers. The next lakh mostly reaches people who
already saw the ad — fewer new customers. By the fifth lakh, everyone reachable has been
reached; extra money buys almost nothing. That's saturation.

So the model fits a curve that rises steeply then flattens. Where a channel sits on its
curve — steep part (more budget pays off) or flat part (saturated) — **is literally the
"where should the next rupee go" answer.**

### Why Bayesian?

- Weekly data is small (200 rows) and channels are correlated → point estimates are unstable.
- Priors let you encode marketing knowledge ("TV decay is probably 0.5–0.8").
- You get uncertainty: "Search ROI is 2.1x, 94% credible interval [1.6, 2.7]" — an honest
  basis for a budget decision. This is your strongest interview talking point.

## 3. The workflow

1. **Data prep** — one row per week: sales, spend per channel, controls. (Notebook 01)
2. **Specify model** — choose adstock + saturation forms, priors, seasonality. (Notebook 02)
3. **Fit** — MCMC sampling (NUTS). Takes 10–40 min on a laptop.
4. **Validate** — convergence diagnostics (r_hat < 1.01, no divergences), posterior
   predictive check (does simulated sales look like actual?), out-of-sample fit.
5. **Decompose** — split each week's sales into baseline + per-channel contributions.
6. **ROI** — channel contribution ÷ channel spend.
7. **Optimize** — reallocate budget along saturation curves to maximize predicted sales.

## 4. Vocabulary you must own

| Term | Meaning |
|---|---|
| KPI / target | The thing you model (weekly revenue here) |
| Adstock / carryover | Lagged, decaying effect of past spend |
| Saturation / Hill curve | Diminishing returns to spend |
| Baseline | Sales not attributable to media |
| Contribution | Sales attributed to a channel in the decomposition |
| ROI / ROAS | Attributed revenue ÷ spend |
| mROI (marginal ROI) | Return on the *next* dollar — what optimization actually uses |
| Prior / posterior | Belief before / after seeing data (Bayesian) |
| r_hat, divergences | MCMC convergence diagnostics |
| Calibration | Anchoring MMM with experiment results (lift tests) — mention in interviews |

## 5. Interview questions to prepare for

1. *Why MMM over last-click attribution?* → privacy-proof, covers offline, measures incrementality not correlation of clicks.
2. *Why did you pick PyMC over Robyn/Meridian?* → see README; know all three.
3. *How do you know your model isn't garbage?* → convergence diagnostics, posterior predictive checks, out-of-sample validation, ROI estimates within plausible industry ranges, contributions sum sensibly.
4. *Difference between ROI and marginal ROI?* → average vs derivative of the saturation curve; budget decisions use marginal.
5. *Limitations of MMM?* → correlational (not a randomized experiment), needs 2+ years of data, channel collinearity, can't do fine-grained targeting. Gold standard = MMM calibrated with lift tests.
6. *What if two channels always move together?* → multicollinearity → wide posteriors; fixes: priors, combining channels, calibration experiments.

## 6. Going deeper (optional, in order)

1. PyMC-Marketing MMM example notebooks — pymc-marketing.io
2. "Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects" (Jin et al., Google, 2017) — the paper behind modern MMM
3. Robyn docs (facebookexperimental.github.io/Robyn) — to speak to the comparison
4. Meridian docs (developers.google.com/meridian) — geo-hierarchical MMM
