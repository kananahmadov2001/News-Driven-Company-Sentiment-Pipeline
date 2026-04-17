# Final Project SQL Scripts (Cleaned)

These files are organized so a teammate can open them in Snowflake Worksheets and run them in order.

## Recommended run order

1. `01_setup_schema_objects.sql`
   - Creates the schema, helper objects, core tables, and reporting view.
2. `02_seed_companies_and_aliases.sql`
   - Inserts starter companies and aliases.
3. `03_optional_insert_manual_test_article.sql`
   - Optional manual test row to verify the pipeline without Airflow.
4. `04_run_company_matching.sql`
   - Populates `fact_article_company_mentions` from raw articles and aliases.
5. `05_run_baseline_sentiment.sql`
   - Populates `fact_article_sentiment` using a simple rule-based baseline.
6. `06_refresh_daily_mart.sql`
   - Refreshes `mart_company_sentiment_daily` from the fact tables.
7. `07_verify_progress_report_outputs.sql`
   - Main screenshot queries for the progress report.
8. `08_verify_cleaning_checks.sql`
   - Data-quality / cleaning checks.
9. `09_verify_analysis_queries.sql`
   - Simple analysis queries for the progress report.

## Notes

- All scripts assume the class-provided Snowflake objects:
  - Role: `TRAINING_ROLE`
  - Warehouse: `MONKEY_WH`
  - Database: `MONKEY_DB`
  - Schema: `FINAL_PROJECT`
- The transformation scripts are written to be re-runnable.
- The sentiment logic here is only a **baseline** for the progress report. It is not the final sentiment method.
- If Airflow has already loaded articles, you can skip the optional manual article script.
