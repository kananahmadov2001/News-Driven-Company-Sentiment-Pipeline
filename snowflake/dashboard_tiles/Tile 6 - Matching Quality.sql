USE ROLE TRAINING_ROLE;
USE WAREHOUSE MONKEY_WH;
USE DATABASE MONKEY_DB;
USE SCHEMA FINAL_PROJECT;

-- Tile 6 should measure matching coverage at the article grain:
--   total_articles    = unique ingested articles/events
--   matched_articles  = unique articles/events with >= 1 company match
--   unmatched_articles = total - matched
--
-- IMPORTANT: compute totals and matches from the same base datasets.
-- Legacy path: raw_articles + fact_article_company_mentions
-- Realtime path: article_company_match_base (event-level), where company_id IS NOT NULL means matched.
WITH legacy_counts AS (
    SELECT
        'legacy' AS ingest_path,
        COUNT(DISTINCT a.article_id) AS total_articles,
        COUNT(DISTINCT CASE WHEN m.article_id IS NOT NULL THEN a.article_id END) AS matched_articles
    FROM raw_articles a
    LEFT JOIN fact_article_company_mentions m
      ON a.article_id = m.article_id
),
realtime_counts AS (
    SELECT
        'realtime' AS ingest_path,
        COUNT(DISTINCT event_id) AS total_articles,
        COUNT(DISTINCT CASE WHEN company_id IS NOT NULL THEN event_id END) AS matched_articles
    FROM article_company_match_base
),
combined AS (
    SELECT * FROM legacy_counts
    UNION ALL
    SELECT * FROM realtime_counts
)
SELECT
    SUM(total_articles) AS total_articles,
    SUM(matched_articles) AS matched_articles,
    SUM(total_articles) - SUM(matched_articles) AS unmatched_articles
FROM combined;
