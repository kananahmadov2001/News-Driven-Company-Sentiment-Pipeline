# Real-Time Migration Plan (Airflow Batch -> Kafka + Spark Streaming)

## Why migrate
Your existing Snowflake model and downstream dashboard logic are already valuable. The migration focuses on **upstream ingestion and processing latency**:

- Keep Snowflake warehouse + core tables.
- Shift acquisition from Airflow-triggered batch pulls to continuous event ingestion.
- Process articles continuously in micro-batches (near-real-time, class-appropriate).

This supports CSE 5114's real-time/distributed systems requirement while preserving prior work.

## Target architecture

1. **Producer layer (Python service)**
   - Poll source APIs/feeds every 30-60 seconds.
   - Detect unseen articles (URL hash/event id dedup).
   - Publish normalized events to Kafka topic: `raw_news_articles`.

2. **Streaming processor (Spark Structured Streaming)**
   - Consume Kafka events.
   - Clean and normalize fields.
   - Deduplicate stories.
   - Match article text to companies (aliases from Snowflake).
   - Compute sentiment score.
   - Write article-level and aggregate outputs to Snowflake.

3. **Serving/storage layer (Snowflake)**
   - `article_company_match` (article -> company + sentiment)
   - `mart_company_sentiment_minute` (rolling minute aggregates)
   - `mart_company_sentiment_hour` (hourly aggregates)
   - Existing dashboard queries can pivot from daily to minute/hour marts.

## Demo-ready operating model

For LinuxLab's limited session duration, run this sequence:

1. **Smoke path**: publish exactly one synthetic event with Python to prove Kafka -> Spark -> Snowflake.
2. **Backfill path**: run one-shot GDELT backfill for 7/14/30 days (configurable caps) to preload demo data.
3. **Live tail path**: keep GDELT live producer running for near-real-time updates.

This avoids demo risk from quiet external feeds while still satisfying real-time architecture goals.

## Why Spark for this project
- Team is already using Python and SQL-centric transformations.
- Structured Streaming offers a familiar DataFrame model.
- Near-real-time micro-batch cadence (30-60 sec) is easy to explain and defend.
- Lower operational complexity than full Flink adoption for class timeline.

## Migration phases (recommended)

### Phase 1: Parallel path (1-2 days)
- Keep Airflow DAG active as fallback.
- Stand up Kafka topic + run producer script.
- Validate event counts and duplicate rate.

### Phase 2: Streaming job + dual-write validation (2-4 days)
- Run Spark micro-batch job every ~45 seconds.
- Load to new realtime mart tables.
- Compare daily rollups from streaming vs current Airflow outputs.

### Phase 3: Cutover (1 day)
- Update dashboard to read realtime marts.
- Reduce Airflow job to backup/reconciliation mode.
- Add quick runbook for restart/recovery.

## Operational expectations
- **Latency target**: 1-2 minutes from source publish to Snowflake mart update.
- **Fault tolerance**:
  - Kafka retains raw events for replay.
  - Spark checkpoint directory enables restart without data loss.
- **Quality controls**:
  - URL hash dedup + event_id dedup.
  - Null/invalid field filtering.
  - Periodic reconciliation query against raw events.

## Files added in this repo
- `streaming/producer/news_producer.py` - source polling publisher to Kafka.
- `streaming/producer/smoke_event_producer.py` - one-shot synthetic event publisher.
- `streaming/producer/gdelt_backfill.py` - one-shot historical backfill publisher.
- `streaming/processor/spark_news_stream.py` - Spark streaming processor to Snowflake.
- `streaming/sql/01_create_realtime_tables.sql` - realtime table DDL.
- `streaming/requirements.txt` - Python dependencies.

## Suggested demo narrative for presentation
1. Show smoke event arriving end-to-end.
2. Show backfill preloading enough historical examples.
3. Show live producer publishing new updates.
4. Show minute-level Snowflake aggregates updating.
