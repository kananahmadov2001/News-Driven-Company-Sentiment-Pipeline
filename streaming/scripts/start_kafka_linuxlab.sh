#!/usr/bin/env bash
set -euo pipefail

KAFKA_HOME="${KAFKA_HOME:-/opt/kafka}"
KAFKA_CONFIG="${KAFKA_CONFIG:-$HOME/kafka-server.properties}"
KAFKA_LOG_DIR="${KAFKA_LOG_DIR:-$HOME/kafka-local-logs}"
BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$KAFKA_LOG_DIR"

if bash "$SCRIPT_DIR/check_kafka_linuxlab.sh" >/tmp/kafka_check_$$.log 2>&1; then
  echo "Kafka appears healthy at ${BOOTSTRAP}. Skipping startup."
  cat /tmp/kafka_check_$$.log
  rm -f /tmp/kafka_check_$$.log
  exit 0
fi

rm -f /tmp/kafka_check_$$.log

nohup "$KAFKA_HOME/bin/kafka-server-start.sh" "$KAFKA_CONFIG" > "$HOME/kafka-server.out" 2>&1 &
sleep 3

echo "Kafka start requested. Check logs: $HOME/kafka-server.out"
echo "Run: bash $SCRIPT_DIR/check_kafka_linuxlab.sh"
