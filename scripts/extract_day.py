"""Copy one GA4 daily shard into the sandbox raw dataset, without Airflow.

Mirrors the DAG's extract_day_partition task, for local testing:

    python scripts/extract_day.py 20201101 [20201102 ...]

Requires GCP_PROJECT_ID env var and gcloud ADC.
"""

import os
import sys

from google.cloud import bigquery

SOURCE_DATASET = "bigquery-public-data.ga4_obfuscated_sample_ecommerce"
RAW_DATASET = "ga4_raw"


def extract_day(client: bigquery.Client, project: str, ds_nodash: str) -> str:
    dataset_ref = bigquery.Dataset(f"{project}.{RAW_DATASET}")
    dataset_ref.location = "US"
    client.create_dataset(dataset_ref, exists_ok=True)

    dest_table = f"{project}.{RAW_DATASET}.events_{ds_nodash}"
    job = client.copy_table(
        f"{SOURCE_DATASET}.events_{ds_nodash}",
        dest_table,
        job_config=bigquery.CopyJobConfig(write_disposition="WRITE_TRUNCATE"),
    )
    job.result()
    return dest_table


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    project = os.environ["GCP_PROJECT_ID"]
    client = bigquery.Client(project=project)
    for ds_nodash in sys.argv[1:]:
        table = extract_day(client, project, ds_nodash)
        rows = client.get_table(table).num_rows
        print(f"{table}: {rows:,} rows")
