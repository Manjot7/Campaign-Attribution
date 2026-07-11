# Does Paid Traffic Cause Higher Purchase Conversion?

*One-page writeup — campaign attribution pipeline (GA4 → BigQuery → dbt → Airflow → DoWhy → MetricFlow → Looker Studio)*

## The causal question

Sessions arriving at the Google Merchandise Store from paid campaigns convert at a different rate than organic/direct sessions. A dashboard reports that gap as campaign performance. But paid campaigns don't reach a random sample of users — they reach particular devices, countries, and returning-visitor segments that convert differently regardless. **Is the paid-vs-organic conversion gap caused by the campaigns, or is it selection?**

- **Treatment**: `is_paid` — session arrived via a paid medium (`cpc`/`cpm`/`ppc`/`paid`)
- **Outcome**: `converted` — session contained a purchase event
- **Data**: obfuscated GA4 export, Nov 1 2020 – Jan 31 2021 · 4,295,584 events · **360,129 sessions** · 15,618 paid (4.3%) · 4,848 converted (1.35%)

## Method

Backdoor adjustment (DoWhy) on the session-level mart. Assumed confounders — variables plausibly influencing both channel of arrival and purchase propensity: **device category**, **country** (top-10 + other), and **new-vs-returning status**. Identification assumes no unobserved confounding, which is a strong assumption here (purchase intent itself is unobserved); results are read as a methodology demonstration on obfuscated sample data, not a business finding.

Three estimators were run rather than one, which turned out to be the most important methodological decision in the project.

## The four estimates

| Estimate | Conversion lift (pp) | Reading |
|---|---|---|
| Naive correlation (no adjustment) | **−0.383** | What a dashboard would report |
| ATE — propensity score matching | **−1.261** | ⚠ Known-unstable outlier (see below) |
| ATE — propensity score weighting (governed) | **+0.157** | 95% bootstrap CI **[−0.090, +0.395]** |
| ATE — propensity score stratification | **+0.152** | Independently agrees with weighting |

**The matching outlier.** With 4.3% treated and purely categorical confounders, the propensity model produces only a handful of distinct scores, so nearest-neighbor matching picks arbitrarily among thousands of tied controls. The symptom is instability: across data windows and clip settings, the matching estimate swung from **+5.9pp** to **−1.3pp** while weighting and stratification barely moved. It is kept in the pipeline and dashboard deliberately, labeled as an outlier — a diagnosed bad estimate shown next to trusted ones.

**A second silent failure worth reporting.** DoWhy's weighting estimator clips propensity scores at `min_ps_score = 0.05` by default. Because the treated share is 4.3%, nearly the *entire* score distribution (range 0.014–0.062) sat below the clip and was floored — which quietly neutralized the adjustment and returned ≈ the naive number (−0.36pp). Lowering the clip below the observed range (0.001) was verified against a from-scratch Hajek IPW implementation (identical to 8 decimal places). Estimator defaults are part of the analysis.

**Uncertainty.** Percentile bootstrap on the weighting estimator (200 resamples, propensity model refit per resample, seed 42): point estimate **+0.157pp**, 95% CI **[−0.090pp, +0.395pp]**; 91.5% of resamples positive; bootstrap SD 0.129pp.

## Finding

**No detectable causal effect of paid exposure on conversion in this dataset.** The naive gap (−0.38pp, paid *appearing worse*) is explained by the observed confounders: after adjustment the effect is +0.16pp with a confidence interval spanning zero. The practical story a stakeholder should take from the dashboard: the raw paid-vs-organic comparison misstates campaign impact — here it flips the sign — and the governed `causal_lift_estimate` metric, not the raw gap, is the number to quote.

*Caveats: obfuscated demo data (many source/geo values are `<Other>`/NULL); no unobserved-confounding control; conclusions are about the method, not Google's marketing.*
