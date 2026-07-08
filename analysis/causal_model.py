"""DoWhy causal analysis: does paid traffic cause higher purchase conversion?

Estimates the ATE of paid exposure (is_paid) on conversion (converted) from
the session mart, next to the naive correlation, and writes both to
`<project>.analysis.causal_estimates` for the semantic layer / dashboard.

Run standalone (the Airflow causal_model task runs exactly this):

    python analysis/causal_model.py

Requires GCP_PROJECT_ID env var and gcloud ADC. The output table is written
with a load job (WRITE_TRUNCATE) because BigQuery Sandbox forbids DML.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
from dowhy import CausalModel
from google.cloud import bigquery

SESSIONS_TABLE = "dbt_campaign_attribution_marts.fct_sessions"
RESULTS_DATASET = "analysis"
RESULTS_TABLE = "causal_estimates"
TOP_N_COUNTRIES = 10

# Obfuscated GA4 data: '<Other>' / NULL values are expected. They are kept as
# their own confounder category rather than dropped, so the treated and
# control groups stay comparable.


def load_sessions(client: bigquery.Client) -> pd.DataFrame:
    query = f"""
        select
            is_paid,
            converted,
            device_category,
            geo_country,
            is_new_user,
            session_date
        from `{client.project}.{SESSIONS_TABLE}`
    """
    return client.query(query).to_dataframe()


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """One-hot encode confounders; return (model_df, confounder_columns)."""
    out = pd.DataFrame(
        {
            "is_paid": df["is_paid"].astype(int),
            "converted": df["converted"].astype(int),
            "is_new_user": df["is_new_user"].astype(int),
        }
    )

    device = pd.get_dummies(
        df["device_category"].fillna("unknown"), prefix="device", dtype=int
    )

    top = df["geo_country"].value_counts().head(TOP_N_COUNTRIES).index
    country = pd.get_dummies(
        df["geo_country"].where(df["geo_country"].isin(top), "other_country"),
        prefix="geo",
        dtype=int,
    )
    # column names must be valid identifiers for dowhy's formula handling
    country.columns = [
        c.replace(" ", "_").replace("<", "").replace(">", "") for c in country.columns
    ]

    out = pd.concat([out, device, country], axis=1)
    confounders = ["is_new_user"] + list(device.columns) + list(country.columns)
    return out, confounders


def naive_difference(df: pd.DataFrame) -> float:
    """Raw correlation: P(convert | paid) - P(convert | not paid)."""
    grouped = df.groupby("is_paid")["converted"].mean()
    return float(grouped.get(1, float("nan")) - grouped.get(0, float("nan")))


def estimate_ate(model_df: pd.DataFrame, confounders: list[str], method: str) -> float:
    model = CausalModel(
        data=model_df,
        treatment="is_paid",
        outcome="converted",
        common_causes=confounders,
    )
    estimand = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(
        estimand, method_name=method, target_units="ate"
    )
    return float(estimate.value)


def refute_placebo(
    model_df: pd.DataFrame, confounders: list[str], method: str, simulations: int = 10
) -> float:
    """Placebo treatment refuter: the ATE should collapse toward zero when the
    treatment is replaced with noise. Returns the placebo 'effect'."""
    model = CausalModel(
        data=model_df,
        treatment="is_paid",
        outcome="converted",
        common_causes=confounders,
    )
    estimand = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(estimand, method_name=method, target_units="ate")
    refutation = model.refute_estimate(
        estimand,
        estimate,
        method_name="placebo_treatment_refuter",
        placebo_type="permute",
        num_simulations=simulations,
    )
    return float(refutation.new_effect)


def run_analysis(client: bigquery.Client) -> pd.DataFrame:
    # Load the session mart
    df = load_sessions(client)
    print(f"Loaded {len(df):,} sessions ({df['session_date'].min()} → {df['session_date'].max()})")

    # Encode confounders
    model_df, confounders = prepare(df)
    print(f"Confounders: {len(confounders)} columns after one-hot encoding")

    # Naive correlation, for reference
    naive = naive_difference(model_df)
    print(f"Naive difference: {naive:+.4f} ({naive * 100:+.2f} pp)")

    rows = []
    now = datetime.now(timezone.utc)
    common = {
        "run_at": now,
        "naive_difference": naive,
        "n_sessions": len(df),
        "n_paid": int(model_df["is_paid"].sum()),
        "n_converted": int(model_df["converted"].sum()),
        "data_start": df["session_date"].min(),
        "data_end": df["session_date"].max(),
    }

    # Backdoor-adjusted ATE, two estimators as a robustness check
    for method, label in [
        ("backdoor.propensity_score_matching", "propensity_score_matching"),
        ("backdoor.propensity_score_weighting", "propensity_score_weighting"),
    ]:
        ate = estimate_ate(model_df, confounders, method)
        print(f"ATE ({label}): {ate:+.4f} ({ate * 100:+.2f} pp)")
        rows.append({"method": label, "ate": ate, **common})

    return pd.DataFrame(rows)


def write_results(client: bigquery.Client, results: pd.DataFrame) -> str:
    dataset = bigquery.Dataset(f"{client.project}.{RESULTS_DATASET}")
    dataset.location = "US"
    client.create_dataset(dataset, exists_ok=True)

    table_id = f"{client.project}.{RESULTS_DATASET}.{RESULTS_TABLE}"
    job = client.load_table_from_dataframe(
        results,
        table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
    )
    job.result()
    return table_id


def main() -> None:
    # Connect to BigQuery
    project = os.environ["GCP_PROJECT_ID"]
    client = bigquery.Client(project=project)
    print(f"Connected to BigQuery project: {project}")

    # Estimate effects
    results = run_analysis(client)
    print(results[["method", "ate", "naive_difference", "n_sessions", "n_paid"]])

    # Persist for the semantic layer / dashboard
    table_id = write_results(client, results)
    print(f"Wrote {len(results)} rows to {table_id}")


if __name__ == "__main__":
    main()
