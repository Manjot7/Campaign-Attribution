{{
    config(
        materialized='table'
    )
}}

/*
    Session grain: one row per (user_pseudo_id, ga_session_id).
    This is the analysis table for the causal model:
      treatment  = is_paid (from traffic medium)
      outcome    = converted (purchase event in session)
      confounders = device_category, geo_country, is_new_user
    Skeleton version — confounder set will be refined in build phase 2.

    Full rebuild (not incremental) on purpose: sessions can span midnight, so
    a per-day incremental aggregate would duplicate any session that crosses a
    date boundary. The staging layer carries the incremental load; this mart
    re-aggregates the (small) staged table each run. Plain CREATE OR REPLACE
    is also DDL, which BigQuery Sandbox allows (it forbids DML).
    A session is attributed to the date of its first event.
*/

select
    session_key,
    user_pseudo_id,
    min(event_date_key) as session_date_key,
    min(event_date) as session_date,
    min(event_at) as session_start_at,

    -- treatment: paid vs organic/direct exposure
    logical_or(traffic_medium in ('cpc', 'cpm', 'ppc', 'paid')) as is_paid,

    -- first-touch attribution (earliest non-null value in the session)
    array_agg(traffic_medium ignore nulls order by event_at limit 1)[safe_offset(0)] as first_touch_medium,
    array_agg(traffic_source ignore nulls order by event_at limit 1)[safe_offset(0)] as first_touch_source,
    array_agg(traffic_campaign ignore nulls order by event_at limit 1)[safe_offset(0)] as first_touch_campaign,

    -- outcome
    logical_or(event_name = 'purchase') as converted,
    sum(coalesce(purchase_revenue_usd, 0)) as session_revenue_usd,

    -- confounders
    any_value(device_category) as device_category,
    any_value(geo_country) as geo_country,
    logical_or(event_name = 'first_visit') as is_new_user

from {{ ref('stg_ga4__events') }}
group by session_key, user_pseudo_id
