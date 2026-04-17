#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

if ss -lnt | awk '{print $4}' | grep -q ':9092$'; then
  echo "Kafka listener detected on :9092"
else
  echo "No listener on :9092"
fi

echo "Listing topics from ${BOOTSTRAP}"
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list || true
