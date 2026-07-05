# Data Dictionary

Source: [sibylhe/mmm_stan](https://github.com/sibylhe/mmm_stan) — anonymized US retailer,
weekly data Aug 2014 onward (200+ weeks). Notebook 01 downloads `data.csv` automatically.

## Column groups

| Prefix / column | Meaning |
|---|---|
| `wk_strt_dt` | Week start date (the time index) |
| `sales` | Weekly sales revenue ($) — the KPI we model |
| `mdsp_*` | **Media spend** ($) per channel per week — main predictors |
| `mdip_*` | Media impressions per channel (same channels; alternative to spend) |
| `me_*` | Macro-economic controls |
| `st_ct` | Store count (distribution) |
| `mrkdn_*` | Markdown / discount value (promo intensity) |
| `hldy_*` | Holiday dummy flags (1 = that week contains the holiday) |
| `seas_*` | Seasonality dummy flags |

## Media channels (the `mdsp_` suffixes)

| Suffix | Channel | Our grouping in notebook 01 |
|---|---|---|
| `dm` | Direct mail | print_mail |
| `inst` | Newspaper insert | print_mail |
| `nsp` | Newspaper ad | print_mail |
| `audtr` | Traditional radio | audio |
| `auddig` | Digital audio | audio |
| `vidtr` | Traditional video (TV) | tv |
| `viddig` | Digital video (YouTube etc.) | digital_video |
| `so` | Social media | social |
| `on` | Online display | display |
| `sem` | Search engine marketing | search |

Why group 10 → 7? With ~200 weekly observations, fewer channels means more data per
parameter and less collinearity. Grouping decisions like this are a legitimate modeling
choice you should be able to defend.

## Key controls we keep

- `me_ics_all` — consumer sentiment index (macro demand)
- `me_gas_dpg` — gas price $/gallon (consumer spending power)
- `st_ct` — store count
- `mrkdn_valadd_edw`, `mrkdn_pdm` — markdown/promo intensity
- Selected `hldy_*` flags (Black Friday, Christmas, Prime Day, Thanksgiving, July 4th)

Yearly seasonality is handled inside the model with Fourier terms, so we drop `seas_*` dummies.
