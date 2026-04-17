USE ROLE TRAINING_ROLE;
USE WAREHOUSE MONKEY_WH;
USE DATABASE MONKEY_DB;
USE SCHEMA FINAL_PROJECT;

-- =========================================================
-- 01a_dashboard_refresh_task.sql
--
-- Purpose:
-- Refresh the dashboard reporting tables every 10 minutes.
--
-- IMPORTANT:
-- This task refreshes the TABLES USED BY THE DASHBOARD.
-- It does NOT run the Airflow DAG.
-- It does NOT generate sentiment by itself.
--
-- So your correct workflow is:
-- 1) Airflow ingests new articles
-- 2) run 05c_run_ai_sentiment.sql
-- 3) run 06_refresh_daily_mart.sql
-- 4) this task refreshes the reporting tables every 10 mins
-- =========================================================

CREATE OR REPLACE TASK task_refresh_dashboard_tables_10m
  WAREHOUSE = MONKEY_WH
  SCHEDULE = '10 MINUTES'
  COMMENT = 'Refresh presentation dashboard reporting tables every 10 minutes using ai_sentiment_v1 outputs'
AS
BEGIN
    -- Tile 1
    CREATE OR REPLACE TABLE rpt_company_article_volume AS
    SELECT
        c.company_id,
        c.ticker,
        c.company_name,
        COUNT(DISTINCT m.article_id) AS article_count,
        CURRENT_TIMESTAMP() AS refreshed_at
    FROM fact_article_company_mentions m
    JOIN dim_companies c
      ON m.company_id = c.company_id
    GROUP BY 1, 2, 3;

    -- Tile 2b / 2c
    CREATE OR REPLACE TABLE rpt_company_sentiment_summary AS
    SELECT
        c.company_id,
        c.ticker,
        c.company_name,
        COUNT(*) AS scored_articles,
        ROUND(AVG(s.sentiment_score), 3) AS avg_sentiment,
        COUNT_IF(s.sentiment_label = 'positive') AS positive_count,
        COUNT_IF(s.sentiment_label = 'neutral') AS neutral_count,
        COUNT_IF(s.sentiment_label = 'negative') AS negative_count,
        CURRENT_TIMESTAMP() AS refreshed_at
    FROM fact_article_sentiment s
    JOIN dim_companies c
      ON s.company_id = c.company_id
    WHERE s.model_name = 'ai_sentiment_v1'
    GROUP BY 1, 2, 3;

    -- Tile 3
    CREATE OR REPLACE TABLE rpt_daily_trend AS
    SELECT
        metric_date,
        SUM(article_count) AS total_articles,
        ROUND(AVG(avg_sentiment), 3) AS avg_sentiment_across_companies,
        CURRENT_TIMESTAMP() AS refreshed_at
    FROM mart_company_sentiment_daily
    GROUP BY 1;

    -- Optional support tile
    CREATE OR REPLACE TABLE rpt_sentiment_examples AS
    SELECT
        c.ticker,
        c.company_name,
        s.sentiment_label,
        s.sentiment_score,
        a.published_at,
        a.source_name,
        a.title,
        a.url,
        s.reasoning,
        CURRENT_TIMESTAMP() AS refreshed_at
    FROM fact_article_sentiment s
    JOIN dim_companies c
      ON s.company_id = c.company_id
    JOIN raw_articles a
      ON s.article_id = a.article_id
    WHERE s.model_name = 'ai_sentiment_v1';
END;