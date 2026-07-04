# PRD: Campaign Attribution & Retention Pipeline

## Tech Stack at a Glance

| Layer | Tool | Status |
|---|---|---|
| Data source | GA4 sample ecommerce dataset (BigQuery public data) | Feasible |
| Warehouse | BigQuery Sandbox | Feasible, free |
| Orchestration | Apache Airflow (local, Docker/Astro CLI) | Feasible, free |
| Transformation | dbt Core + dbt-bigquery | Feasible, free |
| Causal inference | DoWhy (primary), scikit-uplift (optional) | Feasible, free |
| Semantic layer | dbt Semantic Layer / MetricFlow | Feasible, free (Apache 2.0 since Oct 2025) |
| Visualization | Looker Studio or Metabase | Feasible, free |
| Real Looker/LookML | Optional bonus only | Sales-gated, not the core path |

## Overview
An end-to-end analytics pipeline built around a real causal marketing question, using GA4 event data from the Google Merchandise Store. Demonstrates data engineering (Airflow, dbt), causal inference, and semantic/BI layer skills in one coherent build rather than as separate disconnected exercises.

## Objective
Does paid campaign traffic cause higher purchase conversion at the Google Merchandise Store, or does it just capture users who were converting anyway.

## Scope / Non-Goals
- This is a portfolio demonstration, not a production pipeline. The dataset is static and historical; the Airflow DAG is structured to resemble incremental loading, but it is not processing live traffic.
- The dataset is obfuscated for privacy, so treat the causal finding as a methodology demonstration, not a genuine business recommendation to present as fact.
- Real Looker/LookML access is a bonus if you get it, not something to block the project on. Access requires a Google Cloud sales form with an unpredictable timeline, so the core build uses the dbt Semantic Layer instead.

## Success Criteria
- Airflow DAG running an incremental dbt build against the BigQuery marts
- dbt project with staging and mart models, all tests passing
- DoWhy causal effect estimate (ATE) for paid exposure on conversion, shown next to naive correlation
- MetricFlow semantic layer with 3 to 5 governed metrics
- Dashboard (Looker Studio or Metabase) surfacing channel performance and the causal estimate together

## Data Source
**Primary**: `bigquery-public-data.ga4_obfuscated_sample_ecommerce`. Google Merchandise Store, November 1 2020 to January 31 2021, roughly 4.3 million events across 92 daily tables, obfuscated GA4 export. Access through BigQuery Sandbox, free, no billing required, well within the free 1TB/month scan limit.

**Caveat**: fields are obfuscated for privacy, so some values will show as `<Other>` or NULL. This is expected, not a data quality bug you introduced. Worth one line in the writeup so it doesn't read as an oversight.

## Architecture / Tool Stack

### Ingestion
Static historical dataset, but structure the Airflow DAG to pull one date partition (`events_YYYYMMDD`) at a time rather than the whole table at once. This simulates a real incremental pipeline and gives you something honest to say about incremental models in an interview.

### Transformation: dbt Core + dbt-bigquery adapter
- Staging models flatten the nested `event_params` and `items` arrays via UNNEST
- Mart models build a session-level table: treatment flag (paid vs organic/direct, from `traffic_source.medium`), outcome flag (purchase conversion), confounders (`device.category`, `geo.country`, new vs returning from the `first_visit` event)
- dbt tests: not-null, accepted values, relationships between staging and marts

### Orchestration: Apache Airflow
Run locally via Docker Compose or Astronomer's free Astro CLI. DAG shape: extract_day_partition, dbt_run, dbt_test, causal_model, refresh_semantic_layer.

### Causal Inference
DoWhy as the primary tool: backdoor adjustment / propensity score matching for the ATE estimate of paid exposure on conversion. Optional stretch: scikit-uplift for a lightweight uplift/targeting model on top (lighter dependency footprint than CausalML for this specific use case, worth using CausalML only if you specifically want that library name on the resume).

### Semantic Layer: dbt Semantic Layer / MetricFlow
Open sourced under Apache 2.0 in October 2025, so it's now fully free to self-host, and genuinely current given how recent that change is. Define metrics like conversion_rate, sessions, and causal_lift_estimate in YAML as governed, reusable definitions rather than one-off SQL.

### Visualization
Looker Studio (Google's separate free BI product, distinct from enterprise Looker) or Metabase (open source, self-hosted, free), connected to the BigQuery marts or MetricFlow output.

### Note on Real Looker/LookML
If a specific job posting names LookML by name and you want the actual product on your resume, request the Google Cloud Looker trial early since it's gated behind a sales form with an unpredictable timeline. Treat it as a bonus add-on, not a blocker for finishing the project.

## Build Phases
1. BigQuery sandbox setup, explore the raw schema, define treatment/outcome/confounder columns
2. dbt staging and marts, tests passing
3. Airflow DAG wired to dbt, incremental load simulation working end to end
4. DoWhy causal graph, ATE estimate, compared against naive correlation
5. MetricFlow semantic layer plus Looker Studio/Metabase dashboard
6. Writeup and resume bullets

## Risks & Mitigations
- The nested GA4 schema is genuinely fiddly to flatten correctly. Budget extra time for the staging layer, this is normal, not a sign you're doing it wrong.
- Obfuscated data limits how "real" the causal story feels. Be upfront about this in the writeup and frame it as a methodology demonstration rather than a business recommendation.
- Local Airflow (Docker) has real infra overhead. If it becomes a blocker, Dagster or a simple cron-scheduled script is a reasonable fallback, worth a one-line note on the tradeoff in the writeup.

## Deliverables
- GitHub repo: dbt project, Airflow DAG, causal analysis notebook, MetricFlow YAML
- Dashboard link or screenshots
- One-page writeup: causal question, method, finding

## Resume Bullets
- "Built end-to-end analytics pipeline (Airflow, dbt, BigQuery) orchestrating ingestion, transformation, and causal modeling on e-commerce campaign data"
- "Applied DoWhy causal inference to estimate true retention lift from promotional campaigns, controlling for tenure and prior spend, validated against a synthetic dataset with known ground-truth effect"
- "Built a governed semantic layer (dbt Semantic Layer/MetricFlow) and dashboards, separating causal lift from raw correlation for stakeholders"
