"""One-shot GDELT historical backfill producer.

Fetches older articles from GDELT and publishes normalized events to Kafka.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from kafka import KafkaProducer


def dt_to_gdelt(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


def gdelt_to_iso(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def build_event(article: dict) -> dict | None:
    url = article.get("url")
    if not url:
        return None

    seen_date = article.get("seendate", "")
    payload = {
        "provider": "gdelt",
        "provider_article_id": hashlib.sha256(f"{url}|{seen_date}".encode("utf-8")).hexdigest(),
        "published_at": gdelt_to_iso(seen_date),
        "title": article.get("title") or "",
        "description": article.get("socialimage") or article.get("excerpt") or "",
        "content": article.get("socialimage") or article.get("excerpt") or "",
        "source_name": article.get("domain") or article.get("sourcecountry") or "gdelt",
        "url": url,
        "author": "",
        "language": article.get("language") or "en",
        "country": article.get("sourcecountry") or "",
        "raw_json": article,
        "event_ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["event_id"] = hashlib.sha256(
        f"{payload['provider']}|{payload['url']}|{payload['published_at']}".encode("utf-8")
    ).hexdigest()
    return payload


def fetch_window(query: str, start_utc: datetime, end_utc: datetime, max_records: int) -> list[dict]:
    encoded = quote_plus(query)
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={encoded}&mode=ArtList&format=json&maxrecords={max_records}&sort=datedesc"
        f"&startdatetime={dt_to_gdelt(start_utc)}&enddatetime={dt_to_gdelt(end_utc)}"
    )
    req = Request(url)
    with urlopen(req, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("articles", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GDELT backfill producer -> Kafka")
    parser.add_argument("--kafka-bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--topic", default=os.environ.get("BACKFILL_TOPIC", os.environ.get("RAW_ARTICLES_TOPIC", "raw_news_articles")))
    parser.add_argument("--query", default=os.environ.get("GDELT_QUERY", '(Apple OR Microsoft OR NVIDIA OR Tesla OR Amazon)'))
    parser.add_argument("--days-back", type=int, default=int(os.environ.get("BACKFILL_DAYS", "7")))
    parser.add_argument("--window-hours", type=int, default=int(os.environ.get("BACKFILL_WINDOW_HOURS", "6")))
    parser.add_argument("--max-records", type=int, default=int(os.environ.get("BACKFILL_MAX_RECORDS", "250")))
    parser.add_argument("--max-events", type=int, default=int(os.environ.get("BACKFILL_MAX_EVENTS", "5000")))
    parser.add_argument("--sleep-ms", type=int, default=int(os.environ.get("BACKFILL_SLEEP_MS", "500")))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    producer = KafkaProducer(
        bootstrap_servers=[part.strip() for part in args.kafka_bootstrap.split(",")],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
        retries=10,
    )

    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(days=args.days_back)
    cursor = start_utc
    sent = 0
    seen_urls: set[str] = set()

    while cursor < now_utc and sent < args.max_events:
        chunk_end = min(cursor + timedelta(hours=args.window_hours), now_utc)
        articles = fetch_window(args.query, cursor, chunk_end, args.max_records)
        print(f"window={cursor.isoformat()}..{chunk_end.isoformat()} fetched={len(articles)}")

        for article in articles:
            event = build_event(article)
            if not event:
                continue
            url = event["url"].strip().lower()
            if url in seen_urls:
                continue
            seen_urls.add(url)

            if not args.dry_run:
                event_key = hashlib.sha256(event["url"].encode("utf-8")).hexdigest()
                producer.send(args.topic, key=event_key, value=event)
            sent += 1
            if sent >= args.max_events:
                break

        if not args.dry_run:
            producer.flush()
        time.sleep(max(0, args.sleep_ms) / 1000.0)
        cursor = chunk_end

    print(f"Backfill complete sent={sent} dry_run={args.dry_run} topic={args.topic}")


if __name__ == "__main__":
    main()
