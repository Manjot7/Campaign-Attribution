# Dashboard: Channel Performance & Causal Lift

Looker Studio (free) over the BigQuery report views. Looker Studio dashboards
are configured in the web UI, so this folder documents the exact setup; the
queryable surface lives in dbt (`rpt_*` views), so the dashboard itself stays
logic-free.

## Data sources (BigQuery connector)

| Looker Studio data source | BigQuery view | Grain |
|---|---|---|
| `Channel performance` | `dbt_campaign_attribution_marts.rpt_channel_performance` | day × channel × medium |
| `Causal summary` | `dbt_campaign_attribution_marts.rpt_causal_summary` | one row per estimate |

Connect: *Create → Data source → BigQuery → project `campaign-attribution-502801`*,
pick the view, keep default field types (`session_date` should come through as Date).

## Page layout

**Row 1 — governed headline numbers** (scorecards from `Causal summary`):
1. *Naive conversion lift* — `conversion_lift` filtered to `estimate = naive_correlation`
2. *Causal conversion lift (ATE)* — `conversion_lift` filtered to
   `estimate = propensity_score_weighting` (the governed estimator, matching
   the semantic-layer `causal_lift_estimate` metric)
3. Optional third scorecard: `n_sessions` for context.

Put these two side by side — naive says paid looks worse (−0.38pp), the
adjusted estimate says ~no effect (+0.16pp, CI spans zero): the raw gap is
selection, not impact. Label them with `estimate_kind`.

**Estimator comparison bar** (from `Causal summary`): bar chart of
`conversion_lift` by `estimate`, all rows including
`propensity_score_matching` — it is kept deliberately as a **flagged
outlier** (`is_outlier`, `method_caveat` columns): with ~4% treated and
purely categorical confounders, propensity scores collapse to a few tied
values and nearest-neighbor matching picks arbitrarily among thousands of
tied controls. Surface `method_caveat` in the chart tooltip or a text box —
showing a diagnosed bad estimate next to the trusted one is the point.

**Row 2 — channel performance** (from `Channel performance`):
- Time series: `sessions` by `session_date`, breakdown dimension `channel`.
- Time series or bar: `conversion_rate` by `session_date`, breakdown `channel`.

**Row 3 — detail table**: `channel`, `first_touch_medium`, `sessions`,
`conversions`, `conversion_rate`, `revenue_usd`, sorted by sessions desc.

## Notes

- Numbers here are a methodology demonstration on obfuscated sample data, not
  a business finding — say so in a text box on the dashboard.
- The same metric definitions are governed in the dbt semantic layer
  (`dbt/models/semantic/`); the views exist because Looker Studio's free
  connector speaks SQL-to-BigQuery, not MetricFlow. Keep names aligned
  (`conversion_rate`, `causal_lift_estimate` ↔ scorecard 2).
- Metabase alternative: point it at the same two views; nothing else changes.
