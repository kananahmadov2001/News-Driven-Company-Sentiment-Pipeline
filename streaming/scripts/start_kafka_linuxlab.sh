#!/usr/bin/env bash
set -euo pipefail

KAFKA_HOME="${KAFKA_HOME:-/opt/kafka}"
KAFKA_CONFIG="${KAFKA_CONFIG:-$HOME/kafka-server.properties}"
KAFKA_LOG_DIR="${KAFKA_LOG_DIR:-$HOME/kafka-local-logs}"

mkdir -p "$KAFKA_LOG_DIR"

if ss -lnt | awk '{print $4}' | grep -q ':9092$'; then
  echo "Kafka appears already running on :9092. Skipping startup."
  exit 0
fi

nohup "$KAFKA_HOME/bin/kafka-server-start.sh" "$KAFKA_CONFIG" > "$HOME/kafka-server.out" 2>&1 &
sleep 3

echo "Kafka start requested. Check logs: $HOME/kafka-server.out"
