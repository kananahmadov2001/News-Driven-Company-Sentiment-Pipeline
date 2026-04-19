# Snowflake SQL run order (current)

## One-time / rerunnable setup

1. `01_setup_schema_objects.sql`
2. `02_seed_companies_and_aliases.sql`
3. `02b_expand_companies.sql` (optional expansion)
4. `08_create_realtime_base_objects.sql`
5. `09_create_unified_realtime_reporting.sql`

## Optional legacy/manual scripts (kept for compatibility)

- `04_run_company_matching.sql`
- `05c_run_ai_sentiment.sql`
- `06_refresh_daily_mart.sql`
- `07_refresh_dashboard_reporting_tables.sql`

These are not required for each LinuxLab session when using the realtime pipeline + unified dynamic tables.

## Smoke checks

- `tests/pr1_realtime_base_smoke.sql`
- `tests/pr2_unified_reporting_smoke.sql`

## Dashboard tile SQL

Use `snowflake/dashboard_tiles/*.sql`; these query `rpt_*` objects built from unified dynamic tables.
