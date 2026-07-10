"""Campaign attribution pipeline.

Verified end-to-end 2026-07-18 in Docker (apache/airflow:3.0.2 standalone):
manual trigger with logical date 2020-11-03, all six tasks succeeded and the
new shard landed in staging/marts with earlier partitions untouched.
Scheduled catchup backfill has not been exercised yet.

Simulates incremental loading of the static GA4 sample dataset: each DAG run
processes one daily shard (events_YYYYMMDD) for its logical date, then runs
the dbt build for that shard.

Shape (per PRD, with a reporting step split out):
    extract_day_partition
    >> dbt_run >> dbt_test                  (everything except causal reporting)
    >> causal_model                         (DoWhy ATE -> analysis.causal_estimates)
    >> dbt_build_causal_reporting           (views over the causal output)
    >> refresh_semantic_layer               (MetricFlow config validation)

The causal-reporting dbt models are excluded from the main build because they
read the table the causal_model step writes (tag: causal_reporting).
"""

from __future__ import annotations

import os

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task

SOURCE_DATASET = "bigquery-public-data.ga4_obfuscated_sample_ecommerce"
RAW_DATASET = "ga4_raw"
DBT_DIR = "/opt/airflow/dbt"
ANALYSIS_DIR = "/opt/airflow/analysis"

# GA4 sample data covers 2020-11-01 .. 2021-01-31.
DATA_START = pendulum.datetime(2020, 11, 1, tz="UTC")
DATA_END = pendulum.datetime(2021, 1, 31, tz="UTC")

PIPELINE_ENV = {
    "GCP_PROJECT_ID": os.environ.get("GCP_PROJECT_ID", ""),
    # dbt and metricflow read profiles.yml from the mounted project dir
    "DBT_PROFILES_DIR": DBT_DIR,
}


@dag(
    dag_id="campaign_attribution",
    schedule="@daily",
    start_date=DATA_START,
    end_date=DATA_END,
    catchup=False,  # flip to True (with max_active_runs=1) to backfill all 92 days
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["portfolio", "ga4", "dbt"],
)
def campaign_attribution():

    @task
    def extract_day_partition(ds_nodash: str) -> str:
        """Copy one daily shard from the public dataset into our sandbox.

        Copy jobs are free and don't count against the 1 TB/month scan quota.
        Note: BigQuery Sandbox tables expire after 60 days by default; expired
        shards are simply recreated by re-running this task.
        """
        from google.cloud import bigquery

        project = os.environ["GCP_PROJECT_ID"]
        client = bigquery.Client(project=project)

        dataset_ref = bigquery.Dataset(f"{project}.{RAW_DATASET}")
        dataset_ref.location = "US"
        client.create_dataset(dataset_ref, exists_ok=True)

        source_table = f"{SOURCE_DATASET}.events_{ds_nodash}"
        dest_table = f"{project}.{RAW_DATASET}.events_{ds_nodash}"

        job = client.copy_table(
            source_table,
            dest_table,
            job_config=bigquery.CopyJobConfig(write_disposition="WRITE_TRUNCATE"),
        )
        job.result()
        return dest_table

    dbt_vars = "{ds_nodash: {{ ds_nodash }}}"

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"dbt run --project-dir {DBT_DIR} --exclude tag:causal_reporting"
            f" --vars '{dbt_vars}'"
        ),
        env=PIPELINE_ENV,
        append_env=True,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"dbt test --project-dir {DBT_DIR} --exclude tag:causal_reporting"
            f" --vars '{dbt_vars}'"
        ),
        env=PIPELINE_ENV,
        append_env=True,
    )

    causal_model = BashOperator(
        task_id="causal_model",
        bash_command=f"python {ANALYSIS_DIR}/causal_model.py",
        env=PIPELINE_ENV,
        append_env=True,
    )

    dbt_build_causal_reporting = BashOperator(
        task_id="dbt_build_causal_reporting",
        bash_command=(
            f"dbt build --project-dir {DBT_DIR} --select tag:causal_reporting"
            f" --vars '{dbt_vars}'"
        ),
        env=PIPELINE_ENV,
        append_env=True,
    )

    refresh_semantic_layer = BashOperator(
        task_id="refresh_semantic_layer",
        bash_command=f"cd {DBT_DIR} && mf validate-configs",
        env=PIPELINE_ENV,
        append_env=True,
    )

    (
        extract_day_partition(ds_nodash="{{ ds_nodash }}")
        >> dbt_run
        >> dbt_test
        >> causal_model
        >> dbt_build_causal_reporting
        >> refresh_semantic_layer
    )


campaign_attribution()
