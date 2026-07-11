{{
    config(
        materialized='view',
        tags=['causal_reporting']
    )
}}

-- Latest causal estimate per estimation method. Depends on the causal_model
-- pipeline step having written analysis.causal_estimates at least once.
-- The matching estimate is kept but flagged: it is a known outlier here
-- (see method_caveat); propensity_score_weighting is the governed estimator.

select
    method,
    ate,
    naive_difference,
    naive_difference - ate as implied_selection_bias,
    method = 'propensity_score_matching' as is_outlier,
    case
        when method = 'propensity_score_matching' then
            'Known outlier — with a small treated share (~4% of sessions) and purely '
            || 'categorical confounders, the propensity model produces only a handful of '
            || 'distinct scores, so nearest-neighbor matching picks arbitrarily among '
            || 'thousands of tied controls. Weighting and stratification agree near zero; '
            || 'use propensity_score_weighting.'
    end as method_caveat,
    n_sessions,
    n_paid,
    n_converted,
    data_start,
    data_end,
    run_at,
    date(run_at) as run_date
from {{ source('analysis', 'causal_estimates') }}
qualify row_number() over (partition by method order by run_at desc) = 1
