{{
    config(
        materialized='view',
        tags=['causal_reporting']
    )
}}

-- Latest causal estimate per estimation method. Depends on the causal_model
-- pipeline step having written analysis.causal_estimates at least once.

select
    method,
    ate,
    naive_difference,
    naive_difference - ate as implied_selection_bias,
    n_sessions,
    n_paid,
    n_converted,
    data_start,
    data_end,
    run_at,
    date(run_at) as run_date
from {{ source('analysis', 'causal_estimates') }}
qualify row_number() over (partition by method order by run_at desc) = 1
