{{
    config(
        materialized='view'
    )
}}

-- Dashboard-facing daily channel rollup (Looker Studio connects here).

select
    session_date,
    case
        when first_touch_medium in ('cpc', 'cpm', 'ppc', 'paid') then 'paid'
        when first_touch_medium = 'organic' then 'organic'
        when first_touch_medium = 'referral' then 'referral'
        when first_touch_medium = '(none)' or first_touch_medium is null then 'direct'
        else 'other'
    end as channel,
    first_touch_medium,
    count(*) as sessions,
    countif(converted) as conversions,
    safe_divide(countif(converted), count(*)) as conversion_rate,
    round(sum(session_revenue_usd), 2) as revenue_usd
from {{ ref('fct_sessions') }}
group by session_date, channel, first_touch_medium
