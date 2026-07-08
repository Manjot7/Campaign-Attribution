{{
    config(
        materialized='table'
    )
}}

-- MetricFlow requires a day-grain time spine. Covers the GA4 sample window.
-- Plain (unpartitioned) table: DDL only, and no partition expiry in sandbox.

select date_day
from unnest(generate_date_array('2020-11-01', '2021-01-31', interval 1 day)) as date_day
