{{
    config(
        materialized='view',
        tags=['causal_reporting']
    )
}}

-- Dashboard-facing causal-vs-naive comparison: one row per estimation method
-- plus a 'naive_correlation' row, so a single dashboard chart can show the
-- raw gap next to the adjusted estimates. The matching row stays visible but
-- carries is_outlier + method_caveat (tie-based matching pathology).

select
    method as estimate,
    ate as conversion_lift,
    case
        when is_outlier then 'causal (backdoor-adjusted) — KNOWN OUTLIER, see caveat'
        else 'causal (backdoor-adjusted) — governed estimate'
    end as estimate_kind,
    is_outlier,
    method_caveat,
    n_sessions,
    data_start,
    data_end,
    run_at
from {{ ref('fct_causal_estimates') }}

union all

select
    'naive_correlation' as estimate,
    any_value(naive_difference) as conversion_lift,
    'raw correlation (no adjustment)' as estimate_kind,
    false as is_outlier,
    cast(null as string) as method_caveat,
    any_value(n_sessions) as n_sessions,
    any_value(data_start) as data_start,
    any_value(data_end) as data_end,
    any_value(run_at) as run_at
from {{ ref('fct_causal_estimates') }}
