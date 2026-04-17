"""Lightweight article producer.

Polls one or more upstream sources and publishes normalized article events to Kafka.
Designed for near-real-time ingestion (every 30-60 seconds).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from kafka import KafkaProducer


LOGGER = logging.getLogger("news_producer")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_gdelt_dt(value: str) -> str:
    if not value:
        return _now_utc_iso()
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return _now_utc_iso()


@dataclass
class Article:
    provider: str
    provider_article_id: str
    published_at: str
    title: str
    description: str
    content: str
    source_name: str
    url: str
    author: str
    language: str
    country: str
    raw_json: Dict

    @property
    def stable_key(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()

    def as_event(self) -> Dict:
        payload = {
            "provider": self.provider,
            "provider_article_id": self.provider_article_id,
            "published_at": self.published_at,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "source_name": self.source_name,
            "url": self.url,
            "author": self.author,
            "language": self.language,
            "country": self.country,
            "raw_json": self.raw_json,
            "event_ingested_at": _now_utc_iso(),
        }
        payload["event_id"] = hashlib.sha256(
            f"{payload['provider']}|{payload['url']}|{payload['published_at']}".encode("utf-8")
        ).hexdigest()
        return payload


class SourceClient:
    def fetch(self) -> Iterable[Article]:
        raise NotImplementedError


class NewsApiClient(SourceClient):
    def __init__(self, api_key: str, query: str = "stock market OR earnings"):
        self.api_key = api_key
        self.query = query

    def fetch(self) -> Iterable[Article]:
        now = datetime.now(timezone.utc)
        from_dt = (now - timedelta(minutes=15)).isoformat(timespec="seconds")
        query = quote_plus(self.query)
        url = (
            "https://newsapi.org/v2/everything"
            f"?q={query}&from={from_dt}&sortBy=publishedAt&pageSize=100&language=en"
        )
        req = Request(url, headers={"X-Api-Key": self.api_key})
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for idx, row in enumerate(payload.get("articles", [])):
            article_url = row.get("url")
            if not article_url:
                continue
            yield Article(
                provider="newsapi",
                provider_article_id=f"newsapi-{idx}-{row.get('publishedAt', '')}",
                published_at=row.get("publishedAt") or _now_utc_iso(),
                title=row.get("title") or "",
                description=row.get("description") or "",
                content=row.get("content") or "",
                source_name=(row.get("source") or {}).get("name", "unknown"),
                url=article_url,
                author=row.get("author") or "",
                language="en",
                country="",
                raw_json=row,
            )


class RssClient(SourceClient):
    def __init__(self, feed_urls: List[str], provider: str = "rss"):
        self.feed_urls = feed_urls
        self.provider = provider

    def _parse_item(self, item: Dict, fallback_source: str) -> Optional[Article]:
        link = item.get("link")
        if not link:
            return None

        published = item.get("published") or item.get("pubDate")
        published_at = _now_utc_iso()
        if published:
            try:
                published_at = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
            except Exception:
                pass

        provider_id = item.get("id") or item.get("guid") or hashlib.sha256(link.encode("utf-8")).hexdigest()
        return Article(
            provider=self.provider,
            provider_article_id=str(provider_id),
            published_at=published_at,
            title=item.get("title") or "",
            description=item.get("summary") or item.get("description") or "",
            content=item.get("summary") or item.get("description") or "",
            source_name=item.get("source", {}).get("title") if isinstance(item.get("source"), dict) else fallback_source,
            url=link,
            author=item.get("author") or "",
            language="en",
            country="",
            raw_json=item,
        )

    def fetch(self) -> Iterable[Article]:
        import feedparser

        for feed_url in self.feed_urls:
            parsed = feedparser.parse(feed_url)
            fallback_source = (parsed.feed or {}).get("title", self.provider)
            for item in parsed.entries:
                article = self._parse_item(item, fallback_source)
                if article:
                    yield article


class GdeltApiClient(SourceClient):
    def __init__(self, query: str, max_records: int = 100, lookback_minutes: int = 120):
        self.query = query
        self.max_records = max_records
        self.lookback_minutes = lookback_minutes

    def _build_url(self) -> str:
        encoded_query = quote_plus(self.query)
        return (
            "https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={encoded_query}&mode=ArtList&format=json"
            f"&maxrecords={self.max_records}&sort=datedesc&timespan={self.lookback_minutes}min"
        )

    def fetch(self) -> Iterable[Article]:
        req = Request(self._build_url())
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for row in payload.get("articles", []):
            article_url = row.get("url")
            if not article_url:
                continue
            seen_date = row.get("seendate", "")
            title = row.get("title") or ""
            desc = row.get("socialimage") or row.get("excerpt") or ""
            source_name = row.get("domain") or row.get("sourcecountry") or "gdelt"
            yield Article(
                provider="gdelt",
                provider_article_id=hashlib.sha256(f"{article_url}|{seen_date}".encode("utf-8")).hexdigest(),
                published_at=_parse_gdelt_dt(seen_date),
                title=title,
                description=desc,
                content=desc,
                source_name=source_name,
                url=article_url,
                author="",
                language=row.get("language") or "en",
                country=row.get("sourcecountry") or "",
                raw_json=row,
            )


class DedupState:
    """In-memory dedup guard to avoid re-publishing the same URL repeatedly.

    For production, replace with Redis or compacted Kafka topic checkpoint state.
    """

    def __init__(self, max_keys: int = 200_000):
        self.max_keys = max_keys
        self._seen: Dict[str, float] = {}

    def is_new(self, article: Article) -> bool:
        key = article.stable_key
        if key in self._seen:
            return False
        self._seen[key] = time.time()
        if len(self._seen) > self.max_keys:
            sorted_keys = sorted(self._seen.items(), key=lambda kv: kv[1])
            for old_key, _ in sorted_keys[: max(1, self.max_keys // 10)]:
                self._seen.pop(old_key, None)
        return True


class ProducerApp:
    def __init__(self, bootstrap_servers: str, topic: str, source_client: SourceClient):
        self.topic = topic
        self.source_client = source_client
        self.producer = KafkaProducer(
            bootstrap_servers=[server.strip() for server in bootstrap_servers.split(",")],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            acks="all",
            linger_ms=50,
            retries=10,
            compression_type="gzip",
        )
        self.state = DedupState()

    def _run_once(self) -> None:
        fetched = 0
        dedup_dropped = 0
        published = 0
        for article in self.source_client.fetch():
            fetched += 1
            if not self.state.is_new(article):
                dedup_dropped += 1
                continue
            event = article.as_event()
            self.producer.send(self.topic, key=article.stable_key, value=event)
            published += 1
        self.producer.flush()
        LOGGER.info(
            "Producer iteration complete fetched=%s dedup_dropped=%s published=%s",
            fetched,
            dedup_dropped,
            published,
        )

    def run_forever(self, poll_seconds: int) -> None:
        LOGGER.info("Starting producer loop with poll interval=%ss", poll_seconds)
        while True:
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Producer iteration failed: %s", exc)
            time.sleep(poll_seconds)

    def run_once(self) -> None:
        self._run_once()


def build_source_from_env(source: str) -> SourceClient:
    if source == "newsapi":
        api_key = os.environ.get("NEWSAPI_API_KEY")
        if not api_key:
            raise RuntimeError("NEWSAPI_API_KEY is required when --source newsapi is selected")
        query = os.environ.get("NEWS_QUERY", "stock OR shares OR earnings")
        return NewsApiClient(api_key=api_key, query=query)

    if source == "rss":
        urls = os.environ.get(
            "RSS_FEED_URLS",
            "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml,https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        )
        return RssClient(feed_urls=[part.strip() for part in urls.split(",") if part.strip()], provider="rss")

    if source == "gdelt":
        query = os.environ.get(
            "GDELT_QUERY",
            '("stock market" OR earnings OR inflation OR "Federal Reserve" OR Apple OR Microsoft OR NVIDIA)',
        )
        max_records = int(os.environ.get("GDELT_MAX_RECORDS_PER_POLL", "100"))
        lookback_minutes = int(os.environ.get("GDELT_LOOKBACK_MINUTES", "180"))
        gdelt_mode = os.environ.get("GDELT_MODE", "docapi").lower()
        if gdelt_mode == "rssarchive":
            urls = os.environ.get("GDELT_RSS_FEED_URLS", "").strip()
            if not urls:
                raise RuntimeError("Set GDELT_RSS_FEED_URLS when GDELT_MODE=rssarchive")
            return RssClient(feed_urls=[part.strip() for part in urls.split(",") if part.strip()], provider="gdelt")
        return GdeltApiClient(query=query, max_records=max_records, lookback_minutes=lookback_minutes)

    raise ValueError(f"Unsupported source: {source}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Near-real-time news producer -> Kafka")
    parser.add_argument("--kafka-bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--topic", default=os.environ.get("RAW_ARTICLES_TOPIC", "raw_news_articles"))
    parser.add_argument("--poll-seconds", type=int, default=int(os.environ.get("POLL_SECONDS", "60")))
    parser.add_argument("--source", choices=["newsapi", "rss", "gdelt"], default=os.environ.get("SOURCE_TYPE", "gdelt"))
    parser.add_argument("--run-once", action="store_true", help="Run one poll iteration and exit")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    source_client = build_source_from_env(args.source)
    app = ProducerApp(
        bootstrap_servers=args.kafka_bootstrap,
        topic=args.topic,
        source_client=source_client,
    )
    if args.run_once:
        app.run_once()
        return
    app.run_forever(poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()
