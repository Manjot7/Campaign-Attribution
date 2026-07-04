# Campaign Attribution & Retention Pipeline

Does paid campaign traffic *cause* higher purchase conversion at the Google
Merchandise Store, or does it just capture users who were converting anyway?

End-to-end analytics pipeline on the public GA4 ecommerce dataset:
**Airflow → dbt → BigQuery → DoWhy → MetricFlow → Looker Studio**. See
`PRD_campaign_attribution_pipeline.md` for the full plan.

## Layout

```
airflow/
  dags/campaign_attribution.py   DAG: extract >> dbt_run >> dbt_test >> causal_model
                                 >> dbt_build_causal_reporting >> refresh_semantic_layer
                                 (verified end-to-end in Docker; scheduled catchup
                                 backfill not exercised yet)
  docker-compose.yaml            single-container Airflow standalone
dbt/
  models/staging/                stg_ga4__events — flattens nested GA4 export
  models/marts/                  fct_sessions (session grain: treatment/outcome/confounders),
                                 fct_causal_estimates, rpt_* dashboard views
  models/semantic/               MetricFlow semantic models + governed metrics
                                 (sessions, conversions, conversion_rate, revenue,
                                 causal_lift_estimate, naive_conversion_lift)
  models/utilities/              MetricFlow day-grain time spine
  profiles.yml                   BigQuery Sandbox connection (oauth via gcloud ADC)
analysis/
  causal_model.py                DoWhy ATE estimation script (the DAG runs this);
                                 writes analysis.causal_estimates
  causal_analysis.ipynb          narrative notebook: naive vs causal, refutation
dashboard/
  README.md                      Looker Studio setup over the rpt_* views
```

The dataset is static (Nov 2020 – Jan 2021), but the DAG pulls one daily shard
(`events_YYYYMMDD`) per run to simulate an incremental pipeline, and the dbt
models are incremental with `insert_overwrite` on the run's date.

## One-time setup

1. **BigQuery Sandbox** — no billing account needed.
   - Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then:
     ```
     gcloud init                                # create/select a sandbox project
     gcloud auth application-default login      # ADC used by dbt and the DAG
     ```
   - Note your project id; it's needed everywhere as `GCP_PROJECT_ID`.

2. **Python env (dbt)** — from the repo root:
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   $env:GCP_PROJECT_ID = "your-project-id"
   $env:DBT_PROFILES_DIR = "$PWD\dbt"
   .venv\Scripts\dbt debug --project-dir dbt    # verifies the BigQuery connection
   ```

3. **Airflow** — needs [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
   (Airflow doesn't run natively on Windows):
   ```powershell
   cd airflow
   copy .env.example .env      # fill in GCP_PROJECT_ID
   docker compose up
   ```
   UI at http://localhost:8080. Trigger `campaign_attribution` with a logical
   date in the data range, or set `catchup=True` to backfill all 92 days.

## Running the pipeline without Airflow

```powershell
# 1. extract raw shards (one or more days)
.venv\Scripts\python scripts\extract_day.py 20201101 20201102

# 2. transform + test (excluding models that need the causal output)
.venv\Scripts\dbt build --project-dir dbt --exclude tag:causal_reporting --vars '{ds_nodash: 20201101}'

# 3. causal estimates -> analysis.causal_estimates
.venv\Scripts\python analysis\causal_model.py

# 4. views over the causal output
.venv\Scripts\dbt build --project-dir dbt --select tag:causal_reporting

# 5. semantic layer: validate configs / query a governed metric
# ($env:PYTHONUTF8='1' is required on Windows — the mf CLI prints emoji that
#  crash on the default cp1252 console encoding with a misleading
#  "cannot use a string pattern on a bytes-like object" error)
$env:PYTHONUTF8 = '1'
cd dbt; ..\.venv\Scripts\mf validate-configs; ..\.venv\Scripts\mf query --metrics conversion_rate --group-by metric_time__day; cd ..
```

Omit `--vars` in step 2 to process every extracted shard at once. Note
Python is 3.12 (dowhy and dbt-metricflow don't support 3.14 yet).

## Known caveats

- The public dataset is obfuscated: many `traffic_source` / `geo` values are
  `<Other>` or NULL. Expected, not a data quality bug.
- **BigQuery Sandbox forbids DML** (MERGE/INSERT/UPDATE). The incremental
  staging model therefore uses `insert_overwrite` with `copy_partitions: true`,
  which swaps partitions via the free copy-job API (DDL + copy only).
- **Sandbox forces a 60-day expiration on time-based partitions**, which
  silently drops rows dated 2020–2021 the moment they're written. The staging
  table is partitioned by **integer range** on `event_date_key` (YYYYMMDD)
  instead — integer partitions carry no time semantics and survive.
- `fct_sessions` is a full rebuild, not incremental: sessions can span
  midnight, so per-day incremental aggregation would duplicate them. Staging
  carries the incremental load; the mart re-aggregates the small staged table.
- Sandbox tables also expire 60 days after creation — re-running the extract
  and a `dbt build --full-refresh` recreates anything that lapsed.
