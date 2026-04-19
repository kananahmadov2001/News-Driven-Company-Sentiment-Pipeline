# CSE 5114 Final Project: Real-Time Company News Sentiment Pipeline

## Problem statement
This project ingests financial-news events in near real time, detects company mentions, scores article sentiment, and publishes Snowflake reporting objects for dashboard analysis.

## High-level architecture
1. **Producer** (`streaming/producer/gdelt_backfill.py`, `streaming/producer/news_producer.py`) pulls GDELT data (with optional NewsAPI mode) and publishes JSON events to Kafka topic `raw_news_articles`.
2. **Spark Structured Streaming** (`streaming/processor/spark_news_stream.py`) consumes Kafka events, normalizes data, performs alias-based company matching, computes VADER sentiment, and writes micro-batches to Snowflake with:
   - `quote_identifiers=False`
   - `use_logical_type=True`
3. **Snowflake dynamic tables** (`snowflake/09_create_unified_realtime_reporting.sql`) build unified and dashboard-ready reporting objects.
4. **Snowsight dashboard tiles** query `rpt_*` dynamic tables (`snowflake/dashboard_tiles/`).

## Active repository structure
- `streaming/processor/` – Spark streaming application.
- `streaming/producer/` – GDELT backfill/live producer and optional NewsAPI producer mode.
- `streaming/scripts/` – LinuxLab Kafka start/check and Spark checkpoint reset helpers.
- `streaming/sql/01_create_realtime_tables.sql` – realtime sink table setup for Spark writes.
- `snowflake/01_setup_schema_objects.sql` – base schema/tables/views.
- `snowflake/02_seed_companies_and_aliases.sql` – company seed data.
- `snowflake/02b_expand_companies.sql` – optional company/alias expansion.
- `snowflake/08_create_realtime_base_objects.sql` – canonical realtime base table/view.
- `snowflake/09_create_unified_realtime_reporting.sql` – unified + dashboard dynamic tables.
- `snowflake/dashboard_setup/` – dashboard-oriented dynamic-table refresh/check helpers.
- `snowflake/dashboard_tiles/` – Snowsight tile SQL.
- `snowflake/tests/pr1_realtime_base_smoke.sql` and `snowflake/tests/pr2_unified_reporting_smoke.sql` – smoke validation SQL.

## Prerequisites

### Snowflake prerequisites
- Access to a Snowflake account with permission to use/create:
  - role (example: `TRAINING_ROLE`)
  - warehouse (example: `MONKEY_WH`)
  - database (example: `MONKEY_DB`)
  - schema `FINAL_PROJECT`
- Key-pair auth material for Snowflake Python connector.
- Ability to run SQL scripts in Snowsight worksheets.

### LinuxLab prerequisites
- Start LinuxLab compute session using class flow in the [instruction](https://docs.google.com/document/d/1nfv4KBd99ZV8W81O0fPa0i-HJHsjqMDbvCJMSsaQ7w8/edit?usp=sharing) (example shown below uses `server-airflow25 -c 4`).
- Kafka installed at `/opt/kafka`.
- Spark installed at `/opt/spark`.
- 3 terminals available for Kafka, Spark, and producer.

### Python prerequisites
- Python 3.12 compatible virtual environment.
- Install pinned dependencies from `streaming/requirements.txt`.

## Fresh setup from scratch

### 1) Clone and enter repository
```bash
git clone https://github.com/KennyRao/cse5114_final_project.git
cd cse5114_final_project
```

### 2) Start LinuxLab session and Python environment
```bash
server-airflow25 -c 4
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r streaming/requirements.txt
```

### 3) Configure environment file
```bash
cp streaming/env.linuxlab.example.sh env.linuxlab.sh
```
Edit `env.linuxlab.sh` and set your real Snowflake values:
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_PRIVATE_KEY_FILE`
- optional `SNOWFLAKE_PRIVATE_KEY_PWD`

Then load env vars:
```bash
source env.linuxlab.sh
export SPARK_MASTER_URL="spark://${SLURMD_NODENAME}:${SPARK_MASTER_PORT}"
```

### 4) Prepare Snowflake objects (run in order)
Run these scripts in Snowsight worksheets:
1. `snowflake/01_setup_schema_objects.sql`
2. `snowflake/02_seed_companies_and_aliases.sql`
3. `snowflake/02b_expand_companies.sql` (optional)
4. `streaming/sql/01_create_realtime_tables.sql`
5. `snowflake/08_create_realtime_base_objects.sql`
6. `snowflake/09_create_unified_realtime_reporting.sql`

### 5) Optional validation after setup
Run:
- `snowflake/tests/pr1_realtime_base_smoke.sql`
- `snowflake/tests/pr2_unified_reporting_smoke.sql`

## Run the current pipeline (3 terminals)

### Terminal 1: Kafka
```bash
cd ~/projects/cse5114_final_project
source env.linuxlab.sh
bash streaming/scripts/check_kafka_linuxlab.sh
bash streaming/scripts/start_kafka_linuxlab.sh
bash streaming/scripts/check_kafka_linuxlab.sh
```
`start_kafka_linuxlab.sh` is idempotent: it starts Kafka only when needed and always ensures topic `${RAW_ARTICLES_TOPIC:-raw_news_articles}` exists.

### Terminal 2: Spark Structured Streaming
```bash
cd ~/projects/cse5114_final_project
source .venv/bin/activate
source env.linuxlab.sh

spark-submit \
  --master "$SPARK_MASTER_URL" \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1 \
  streaming/processor/spark_news_stream.py
```

### Terminal 3: Ingestion / backfill
Backfill first (resumable):
```bash
cd ~/projects/cse5114_final_project
source .venv/bin/activate
source env.linuxlab.sh
python streaming/producer/gdelt_backfill.py --days-back 14 --window-hours 6 --max-events 100000
```

Then run live ingestion:
```bash
python streaming/producer/news_producer.py --source gdelt --poll-seconds 300
```

Optional source mode:
```bash
python streaming/producer/news_producer.py --source newsapi --poll-seconds 60
```

## Dashboard and reporting instructions

### Reporting lineage
- Spark writes base sink rows to:
  - `ARTICLE_COMPANY_MATCH`
  - `ARTICLE_COMPANY_MATCH_BASE`
  - `MART_COMPANY_SENTIMENT_MINUTE`
- Snowflake dynamic table layer builds:
  - `DT_REALTIME_ARTICLE_COMPANY_MATCH`
  - `DT_UNIFIED_ARTICLE_COMPANY_MENTIONS`
  - `RPT_*` dashboard objects

### Dynamic table refresh behavior
- Dynamic tables are configured with `TARGET_LAG = '5 minutes'` and refresh automatically.
- If you need immediate refresh before grading/demo, run `snowflake/dashboard_setup/01c_start_task_manually.sql`.
- To verify refresh status/history, run `snowflake/dashboard_setup/01d_check_task.sql`.

### Snowsight dashboard refresh
- Open the dashboard that uses SQL in `snowflake/dashboard_tiles/`.
- Refresh tiles/dashboard in Snowsight after new data arrives.

## Current active Snowflake objects

### Database and schema
- `MONKEY_DB.FINAL_PROJECT`

### Base/dimension tables used now
- `DIM_COMPANIES` – tracked companies.
- `DIM_COMPANY_ALIASES` – alias lookup for mention matching.
- `RAW_ARTICLES` – historical/legacy article store used by unified layer.
- `FACT_ARTICLE_COMPANY_MENTIONS` – historical/legacy mention facts used by unified layer.
- `FACT_ARTICLE_SENTIMENT` – historical/legacy sentiment facts used by unified layer.
- `ARTICLE_COMPANY_MATCH` – compatibility sink from Spark.
- `ARTICLE_COMPANY_MATCH_BASE` – canonical append-only realtime sink from Spark.
- `MART_COMPANY_SENTIMENT_MINUTE` – compatibility minute aggregate sink from Spark.

### Dynamic tables used now
- `DT_REALTIME_ARTICLE_COMPANY_MATCH` – deduplicated realtime canonical rows.
- `DT_UNIFIED_ARTICLE_COMPANY_MENTIONS` – unified legacy + realtime reporting grain.
- `RPT_COMPANY_ARTICLE_VOLUME` – dashboard article volume by company.
- `RPT_COMPANY_SENTIMENT_SUMMARY` – dashboard sentiment summary by company.
- `RPT_DAILY_TREND` – dashboard time-series trend.
- `RPT_SENTIMENT_EXAMPLES` – dashboard sample rows.
- `RPT_TOP_SOURCES` – dashboard source distribution.

### Views used now
- `VW_LEGACY_ARTICLE_COMPANY_MENTIONS` – legacy compatibility feed for unified DT.
- `VW_REALTIME_ARTICLE_COMPANY_MENTIONS` – convenience view on realtime DT.
- `VW_UNIFIED_ARTICLE_COMPANY_MENTIONS` – convenience view on unified DT.
- `V_ARTICLE_COMPANY_MATCH_BASE_DUPS` – duplicate visibility helper for canonical key checks.

## Data source notes
- **Primary current source**: GDELT (`gdelt_backfill.py` and `news_producer.py --source gdelt`).
- **Optional source**: NewsAPI mode (`news_producer.py --source newsapi`) if credentials are available.

## Reproducibility and troubleshooting
- If Spark stops, restart Terminal 2; checkpoint path (`CHECKPOINT_PATH`) preserves progress.
- If backfill stops, rerun `gdelt_backfill.py`; cursor resumes from `BACKFILL_CURSOR_FILE`.
- Backfill failed/skipped windows are logged to `BACKFILL_FAILED_WINDOWS_FILE` (JSONL) so they can be inspected and replayed later.
- If Kafka is not reachable, rerun:
  - `bash streaming/scripts/check_kafka_linuxlab.sh`
  - `bash streaming/scripts/start_kafka_linuxlab.sh`
- If Snowflake writes fail, verify env vars and key file path in `env.linuxlab.sh`.
- If dashboard tables look stale, run manual refresh SQL in `snowflake/dashboard_setup/01c_start_task_manually.sql` and then refresh Snowsight tiles.
