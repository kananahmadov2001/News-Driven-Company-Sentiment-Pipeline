# CSE 5114 Final Project

News-driven company sentiment pipeline on **Kafka + Spark + Snowflake**.

This repository now supports three practical demo paths on WashU LinuxLab:
1. **Synthetic smoke test** (publish exactly one event with Python)
2. **Live near-real-time ingestion** (GDELT-first)
3. **Historical backfill** (GDELT one-shot -> Kafka -> Spark -> Snowflake)

---

## 1) LinuxLab assumptions

- LinuxLab home path style: `/home/compute/<netid>/...`
- Repo path (example): `/home/compute/r.weikai/projects/cse5114_final_project`
- Kafka install: `/opt/kafka`
- Spark install: `/opt/spark`
- Java 17 available
- Kafka topic: `raw_news_articles`
- Spark submit package for LinuxLab Spark 4.0.1:
  `org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1`

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

## 3) Environment variables (no secrets in git)

Use the template and fill values in your shell only:

```bash
cp streaming/env.linuxlab.example.sh /tmp/env.linuxlab.sh
# edit /tmp/env.linuxlab.sh with your local values
source /tmp/env.linuxlab.sh
```

Required Snowflake vars (key-pair auth path already supported):
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT`
- `SNOWFLAKE_PRIVATE_KEY_FILE`

> Do **not** switch to password auth unless you intentionally reconfigure.

---

## 4) Kafka startup/checks (avoid duplicate brokers)

### Create LinuxLab broker config/log dir once

```bash
cat > ~/kafka-server.properties <<'EOF'
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
EOF
mkdir -p ~/kafka-local-logs
```

### Check/start safely

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

## 5) Run the Spark streaming processor

```bash
source .venv/bin/activate
source /tmp/env.linuxlab.sh

spark-submit \
  --master "$SPARK_MASTER_URL" \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1 \
  streaming/processor/spark_news_stream.py
```

If you need to replay from earliest after a test reset:

```bash
bash streaming/scripts/reset_checkpoint.sh
export KAFKA_STARTING_OFFSETS=earliest
```

---

## 6) Synthetic smoke test (exactly one event)

Use this whenever external sources are quiet:

```bash
source .venv/bin/activate
source /tmp/env.linuxlab.sh
python streaming/producer/smoke_event_producer.py
```

Expected: script prints it published 1 event.

---

## 7) Live producer (GDELT-first)

```bash
source .venv/bin/activate
source /tmp/env.linuxlab.sh

# Default SOURCE_TYPE=gdelt from env template
python streaming/producer/news_producer.py --source gdelt --poll-seconds 60
```

Optional source modes:
- `--source newsapi` (optional, requires `NEWSAPI_API_KEY`)
- `--source rss` (explicit RSS feed list via `RSS_FEED_URLS`)

---

## 8) Historical backfill (one-shot)

```bash
source .venv/bin/activate
source /tmp/env.linuxlab.sh

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

## 9) Verify data in Kafka

```bash
/opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
  --topic "$RAW_ARTICLES_TOPIC" \
  --from-beginning --max-messages 5
```

---

## 10) Verify data in Snowflake

Example checks in Snowsql:

```sql
SELECT COUNT(*) AS row_count FROM FINAL_PROJECT.article_company_match;

SELECT bucket_minute, company_id, article_count, avg_sentiment
FROM FINAL_PROJECT.mart_company_sentiment_minute
ORDER BY bucket_minute DESC
LIMIT 20;
```

---

## 11) What NOT to do on LinuxLab

- Do not rely on old Reuters RSS defaults.
- Do not commit private keys or secrets.
- Do not rely on Snowflake Spark connector path unless you have validated compatibility with Spark 4.0.1.
- Do not leave checkpoint cleanup as a routine step; only reset when you intentionally want replay behavior.

---

## 12) Useful execution sequence for demos

Open 4 terminals and run in this order:

1. **Terminal A:** Kafka checks/start
2. **Terminal B:** Spark streaming job
3. **Terminal C:** smoke event producer (one event)
4. **Terminal D:** GDELT backfill (short window), then live producer

This guarantees you always have demo-visible data even if live sources are temporarily quiet.
