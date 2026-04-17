#!/usr/bin/env bash
# LinuxLab environment template (no secrets).

export PROJECT_ROOT="$HOME/projects/cse5114_final_project"
export KAFKA_HOME="/opt/kafka"
export SPARK_HOME="/opt/spark"

export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export RAW_ARTICLES_TOPIC="raw_news_articles"
export BACKFILL_TOPIC="raw_news_articles"

export SOURCE_TYPE="gdelt"
export POLL_SECONDS="60"
export LOG_LEVEL="INFO"

# GDELT live/backfill defaults
export GDELT_MODE="docapi"
export GDELT_QUERY='("stock market" OR earnings OR inflation OR "Federal Reserve" OR Apple OR Microsoft OR NVIDIA)'
export GDELT_LOOKBACK_MINUTES="180"
export GDELT_MAX_RECORDS_PER_POLL="100"
# export GDELT_RSS_FEED_URLS="https://example.com/gdelt-rss-feed.xml"

# NewsAPI is optional
# export NEWSAPI_API_KEY=""
# export NEWS_QUERY="stock OR shares OR earnings"

# Spark streaming settings
export PROCESSING_TIME="45 seconds"
export CHECKPOINT_PATH="$HOME/checkpoints/news-stream"
export KAFKA_STARTING_OFFSETS="latest"
export MAX_OFFSETS_PER_TRIGGER="2000"

# Backfill settings
export BACKFILL_DAYS="14"
export BACKFILL_WINDOW_HOURS="6"
export BACKFILL_MAX_RECORDS="250"
export BACKFILL_MAX_EVENTS="5000"
export BACKFILL_SLEEP_MS="500"

# Snowflake (key-pair auth)
export SNOWFLAKE_ACCOUNT="SFEDU02-UNB02139"
export SNOWFLAKE_USER="MONKEY"
export SNOWFLAKE_DATABASE="MONKEY_DB"
export SNOWFLAKE_SCHEMA="FINAL_PROJECT"
export SNOWFLAKE_WAREHOUSE="MONKEY_WH"
export SNOWFLAKE_ROLE="TRAINING_ROLE"
export SNOWFLAKE_AUTHENTICATOR="SNOWFLAKE_JWT"
export SNOWFLAKE_PRIVATE_KEY_FILE="$HOME/airflow25/rsa_key.p8"
# export SNOWFLAKE_PRIVATE_KEY_PWD=""

export COMPANY_ALIAS_TABLE="dim_company_aliases"
export ARTICLE_MATCH_TABLE="article_company_match"
export MART_MINUTE_TABLE="mart_company_sentiment_minute"
