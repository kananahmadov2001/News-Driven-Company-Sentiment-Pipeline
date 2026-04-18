# CSE 5114 Final Project

News-driven company sentiment pipeline on **Kafka + Spark Structured Streaming + Snowflake**.

This repository supports three practical demo paths on WashU LinuxLab:
1. **Synthetic smoke test** (publish exactly one event with Python)
2. **Live near-real-time ingestion** (GDELT-first)
3. **Historical backfill** (GDELT one-shot -> Kafka -> Spark -> Snowflake)

---

## 1) LinuxLab assumptions (current working path)

- Start each LinuxLab session with:
  ```bash
  server-airflow25 -c 4
  ```
- Kafka install: `/opt/kafka`
- Spark install: `/opt/spark`
- Kafka config: `~/kafka-server.properties`
- Kafka log dir: `~/kafka-local-logs`
- Kafka bootstrap: `localhost:9092`
- Topic: `raw_news_articles`
- Spark package required on LinuxLab Spark 4.0.1:
  `org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1`

> Snowflake writes in this repo use the **Snowflake Python connector** path (inside `foreachBatch`) rather than the Spark Snowflake connector. This is intentional for the working LinuxLab Spark 4.0.1 flow.

---

## 2) Python environment setup

```bash
cd /home/compute/$USER/projects/cse5114_final_project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r streaming/requirements.txt
```

---

## 3) Environment variables (repo-local, no secrets in git)

```bash
cp streaming/env.linuxlab.example.sh env.linuxlab.sh
# edit env.linuxlab.sh with your local values (do not commit secrets)
source env.linuxlab.sh
```

Required Snowflake vars for key-pair auth:
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT`
- `SNOWFLAKE_PRIVATE_KEY_FILE`

Keep auth mode as key-pair (`SNOWFLAKE_JWT`) unless you intentionally redesign auth.

---

## 4) Spark master URL check/set (LinuxLab)

Use standalone master format:

```bash
export SPARK_MASTER_URL="spark://${SLURMD_NODENAME}:${SPARK_MASTER_PORT}"
echo "$SPARK_MASTER_URL"
```

If your session startup script already exports these vars, this line simply confirms alignment.

---

## 5) Kafka startup/check (safe, avoids duplicate brokers)

### Create LinuxLab broker config/log dir once

```bash
cat > ~/kafka-server.properties <<'EOF_CFG'
process.roles=broker,controller
node.id=1
listeners=PLAINTEXT://:9092,CONTROLLER://:9093
advertised.listeners=PLAINTEXT://localhost:9092
controller.listener.names=CONTROLLER
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
controller.quorum.voters=1@localhost:9093
inter.broker.listener.name=PLAINTEXT
log.dirs=/home/compute/$USER/kafka-local-logs
num.partitions=3
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
EOF_CFG
mkdir -p ~/kafka-local-logs
```

### Check/start sequence

```bash
bash streaming/scripts/check_kafka_linuxlab.sh
bash streaming/scripts/start_kafka_linuxlab.sh
bash streaming/scripts/check_kafka_linuxlab.sh
```

### Ensure topic exists

```bash
/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --create --if-not-exists --topic "$RAW_ARTICLES_TOPIC" --partitions 3 --replication-factor 1
```

---

## 6) Run Spark streaming processor

```bash
source .venv/bin/activate
source env.linuxlab.sh

spark-submit \
  --master "$SPARK_MASTER_URL" \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1 \
  streaming/processor/spark_news_stream.py
```

If you intentionally want replay behavior from earliest offsets:

```bash
bash streaming/scripts/reset_checkpoint.sh
export KAFKA_STARTING_OFFSETS=earliest
```

---

## 7) Smoke test producer (guaranteed demo path)

```bash
source .venv/bin/activate
source env.linuxlab.sh
python streaming/producer/smoke_event_producer.py
```

Expected: script prints it published exactly 1 event.

---

## 8) GDELT backfill (demo data preload)

```bash
source .venv/bin/activate
source env.linuxlab.sh

python streaming/producer/gdelt_backfill.py \
  --days-back 14 \
  --window-hours 6 \
  --max-records 250 \
  --max-events 5000
```

Dry run (no Kafka writes):

```bash
python streaming/producer/gdelt_backfill.py --days-back 7 --dry-run
```

---

## 9) Live producer (GDELT-first)

```bash
source .venv/bin/activate
source env.linuxlab.sh
python streaming/producer/news_producer.py --source gdelt --poll-seconds 60
```

Optional source modes:
- `--source newsapi` (optional, requires `NEWSAPI_API_KEY`)
- `--source rss` (explicit feed list via `RSS_FEED_URLS`)

---

## 10) Verify results

### Kafka

```bash
/opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --topic "$RAW_ARTICLES_TOPIC" \
  --from-beginning --max-messages 5
```

### Snowflake

```sql
SELECT COUNT(*) AS row_count FROM FINAL_PROJECT.article_company_match;

SELECT bucket_minute, company_id, article_count, avg_sentiment
FROM FINAL_PROJECT.mart_company_sentiment_minute
ORDER BY bucket_minute DESC
LIMIT 20;
```

---

## 11) Presentation-day runbook

1. Start LinuxLab session: `server-airflow25 -c 4`
2. `source env.linuxlab.sh`; confirm `SPARK_MASTER_URL`
3. Verify/start Kafka (`check_kafka_linuxlab.sh`, then `start_kafka_linuxlab.sh` if needed)
4. Start Spark streaming job
5. Run smoke event producer (guarantees end-to-end demo)
6. Verify Snowflake rows
7. Run GDELT backfill for demo volume
8. Optionally run live GDELT producer

---

## 12) What NOT to do

- Do not revert away from Snowflake Python connector writes in the streaming processor.
- Do not remove required `write_pandas` options (`quote_identifiers=False`, `use_logical_type=True`).
- Do not switch key-pair auth away from current working design unless intentionally redesigning.
- Do not restore old Reuters/weak defaults as primary live path.
- Do not commit private keys or secrets.
