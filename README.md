# CSE 5114 Final Project

News-Driven Company Sentiment Pipeline.

## Current direction: near-real-time architecture

The project is migrating from Airflow-centric batch ingestion toward a near-real-time design while keeping Snowflake as the warehouse.

### Architecture

- **Producer service** (`streaming/producer/news_producer.py`)
  - Polls news source(s) every 30-60 seconds.
  - Deduplicates and publishes article events to Kafka topic `raw_news_articles`.
- **Streaming processor** (`streaming/processor/spark_news_stream.py`)
  - Reads Kafka events with Spark Structured Streaming.
  - Cleans and normalizes article fields.
  - Performs alias-based company matching.
  - Applies baseline sentiment scoring.
  - Writes article-level outputs and minute aggregates to Snowflake.
- **Serving layer** (Snowflake)
  - Existing model remains in place.
  - Realtime marts added for dashboarding (`mart_company_sentiment_minute`, `mart_company_sentiment_hour`).

## Repository layout

- `airflow25/` - existing Airflow DAG implementation.
- `snowflake/` - schema setup, transforms, marts, and dashboard SQL.
- `streaming/` - realtime producer/processor scaffold.
- `docs/realtime_migration_plan.md` - migration plan and rollout phases.

## Quick start (streaming path)

1. Install dependencies:
   ```bash
   pip install -r streaming/requirements.txt
   ```
2. Create/verify realtime Snowflake tables:
   ```bash
   snowsql -f streaming/sql/01_create_realtime_tables.sql
   ```
3. Start producer:
   ```bash
   python streaming/producer/news_producer.py --source rss --poll-seconds 60
   ```
4. Start streaming processor:
   ```bash
   spark-submit streaming/processor/spark_news_stream.py
   ```

> For class scope, target near-real-time (30-60 second polling + 30-60 second micro-batches).
