{{
    config(
        materialized='incremental',
        incremental_strategy='insert_overwrite',
        partition_by={
            'field': 'event_date_key',
            'data_type': 'int64',
            'range': {'start': 20201101, 'end': 20210201, 'interval': 1},
            'copy_partitions': true
        },
        on_schema_change='fail'
    )
}}

/*
    Flattens one GA4 event shard per run into typed columns.
    Grain: one row per event.
    The nested event_params array is extracted via correlated subqueries
    (cleaner than UNNEST + GROUP BY for single-key lookups).

    Partitioning is integer-range on event_date_key (YYYYMMDD), not
    time-based on event_date, to work inside BigQuery Sandbox:
      - Sandbox forces a 60-day partition expiration on time-partitioned
        tables, which silently drops these 2020-2021 rows on write.
        Integer-range partitions carry no time semantics, so they survive.
      - Sandbox also forbids DML (MERGE/INSERT), so copy_partitions swaps
        partitions via the free copy-job API instead of a MERGE statement.
*/

with source as (

    select *
    from {{ source('ga4_raw', 'events') }}
    {% if var('ds_nodash') %}
    where _table_suffix = '{{ var("ds_nodash") }}'
    {% endif %}

),

renamed as (

    select
        cast(event_date as int64) as event_date_key,
        parse_date('%Y%m%d', event_date) as event_date,
        timestamp_micros(event_timestamp) as event_at,
        event_name,
        user_pseudo_id,

        (
            select value.int_value
            from unnest(event_params)
            where key = 'ga_session_id'
        ) as ga_session_id,

        -- treatment inputs
        traffic_source.medium as traffic_medium,
        traffic_source.source as traffic_source,
        traffic_source.name as traffic_campaign,

        -- confounder inputs
        device.category as device_category,
        geo.country as geo_country,

        -- outcome / behavior inputs
        ecommerce.purchase_revenue_in_usd as purchase_revenue_usd

    from source

)

select
    *,
    concat(user_pseudo_id, '-', cast(ga_session_id as string)) as session_key
from renamed
where ga_session_id is not null
