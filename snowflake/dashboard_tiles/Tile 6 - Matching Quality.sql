USE ROLE TRAINING_ROLE;
USE WAREHOUSE MONKEY_WH;
USE DATABASE MONKEY_DB;
USE SCHEMA FINAL_PROJECT;

WITH totals AS (
    SELECT
        'legacy' AS ingest_path,
        COUNT(DISTINCT article_id) AS total_articles
    FROM raw_articles

    UNION ALL

    SELECT
        'realtime' AS ingest_path,
        COUNT(DISTINCT event_id) AS total_articles
    FROM article_stream_events
),
matched AS (
    SELECT
        'legacy' AS ingest_path,
        COUNT(DISTINCT article_id) AS matched_articles
    FROM fact_article_company_mentions

    UNION ALL

    SELECT
        'realtime' AS ingest_path,
        COUNT(DISTINCT event_id) AS matched_articles
    FROM article_company_match_base
),
combined AS (
    SELECT
        t.ingest_path,
        t.total_articles,
        COALESCE(m.matched_articles, 0) AS matched_articles
    FROM totals t
    LEFT JOIN matched m
      ON t.ingest_path = m.ingest_path
)
SELECT
    SUM(total_articles) AS total_articles,
    SUM(matched_articles) AS matched_articles,
    SUM(total_articles) - SUM(matched_articles) AS unmatched_articles
FROM combined;
