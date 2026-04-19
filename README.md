# CSE 5114 Final Project

News-driven company sentiment pipeline on **Kafka + Spark Structured Streaming + Snowflake**.

This repo is optimized for LinuxLab 8-hour sessions with a 3-terminal workflow:
1. Kafka broker terminal
2. Spark streaming processor terminal
3. GDELT backfill/live producer terminal

The proven ingestion path remains unchanged:
- Kafka from `/opt/kafka`
- Spark from `/opt/spark`
- Spark submit with package `org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1`
- Spark `foreachBatch` writes to Snowflake via Python connector
- `write_pandas(..., quote_identifiers=False, use_logical_type=True)`

## Architecture (durable + restart-safe)

### Durable base writes (from Spark)
Spark appends matched article/company rows into:
- `article_company_match` (legacy-compatible stream sink)
- `article_company_match_base` (canonical append-only base)
- `mart_company_sentiment_minute` (legacy-compatible minute sink)

If LinuxLab stops, rows already committed in Snowflake remain durable.

### Snowflake downstream (automatic refresh)
Run once:
- `snowflake/08_create_realtime_base_objects.sql`
- `snowflake/09_create_unified_realtime_reporting.sql`

This creates dynamic tables that auto-refresh dashboard-facing objects:
- `dt_realtime_article_company_match` (dedup realtime base)
- `dt_unified_article_company_mentions` (legacy NewsAPI + realtime GDELT/NewsAPI unified)
- `rpt_company_article_volume`
- `rpt_company_sentiment_summary`
- `rpt_daily_trend`
- `rpt_sentiment_examples`
- `rpt_top_sources`

In Snowsight, you only refresh dashboards/tiles (not transformation SQL each session).

## Sentiment model choice

Implemented sentiment in Spark uses **VADER** (`vaderSentiment`):
- Better than tiny keyword baseline (continuous compound scores, negation/intensity handling)
- Lightweight, CPU-friendly for LinuxLab streaming micro-batches
- No paid external API and no large model downloads

## LinuxLab setup

```bash
server-airflow25 -c 4
cd /home/compute/$USER/projects/cse5114_final_project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r streaming/requirements.txt
cp streaming/env.linuxlab.example.sh env.linuxlab.sh
source env.linuxlab.sh
```

Set Spark standalone master URL each session:
```bash
export SPARK_MASTER_URL="spark://${SLURMD_NODENAME}:${SPARK_MASTER_PORT}"
```

## 3-terminal run model

### Terminal 1: Kafka
```bash
source env.linuxlab.sh
bash streaming/scripts/check_kafka_linuxlab.sh
bash streaming/scripts/start_kafka_linuxlab.sh
bash streaming/scripts/check_kafka_linuxlab.sh
```

### Terminal 2: Spark streaming processor
```bash
source .venv/bin/activate
source env.linuxlab.sh

spark-submit \
  --master "$SPARK_MASTER_URL" \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1 \
  streaming/processor/spark_news_stream.py
```

### Terminal 3: Producer (backfill then live)
Backfill (resumable cursor + safe retries/backoff):
```bash
source .venv/bin/activate
source env.linuxlab.sh
python streaming/producer/gdelt_backfill.py --days-back 14 --window-hours 6 --max-events 100000
```

Live GDELT:
```bash
python streaming/producer/news_producer.py --source gdelt --poll-seconds 60
```

Optional NewsAPI mode still works:
```bash
python streaming/producer/news_producer.py --source newsapi --poll-seconds 60
```

## Safe restart / recovery

- If Spark stops, restart Terminal 2. Checkpointing resumes stream progress.
- If backfill stops, rerun `gdelt_backfill.py`; it resumes from cursor file (`BACKFILL_CURSOR_FILE`).
- Snowflake data already written remains available; dynamic tables continue to refresh from durable base objects.

## Verification queries

```sql
SELECT COUNT(*) FROM FINAL_PROJECT.article_company_match_base;
SELECT provider, COUNT(*) FROM FINAL_PROJECT.dt_unified_article_company_mentions GROUP BY 1;
SELECT * FROM FINAL_PROJECT.rpt_company_article_volume ORDER BY article_count DESC;
SELECT * FROM FINAL_PROJECT.rpt_company_sentiment_summary ORDER BY scored_articles DESC;
SELECT * FROM FINAL_PROJECT.rpt_daily_trend ORDER BY metric_date DESC;
```

## What remains preserved between sessions

- All Snowflake base and reporting data
- Dynamic table definitions + refresh behavior
- Backfill cursor checkpoint file (if same LinuxLab filesystem path)

## Notes

- Do not remove or alter the working Snowflake connector write settings.
- Do not replace Kafka + Spark + Snowflake architecture.
- GDELT remains the primary practical source; NewsAPI is optional compatibility path.
