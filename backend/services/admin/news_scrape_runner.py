import asyncio
import logging
import re
from collections.abc import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import NewsArticle
from backend.scrapers.news import (
    ExistingUrlsResolver,
    ScrapedNewsItem,
    scrape_indianexpress_latest,
    scrape_indiatv_latest,
    scrape_livemint_latest,
    scrape_news18_latest,
)
from backend.services.common.domain_errors import DomainValidationError
from backend.services.admin.app_config import record_admin_log


logger = logging.getLogger(__name__)
INDIA_TZ = ZoneInfo("Asia/Kolkata")

_SUPPORTED_SOURCES = {
    "indianexpress": scrape_indianexpress_latest,
    "livemint": scrape_livemint_latest,
    "news18": scrape_news18_latest,
    "indiatv": scrape_indiatv_latest,
}


def _resolve_sources(sources: list[str] | None) -> list[str]:
    if not sources:
        return list(_SUPPORTED_SOURCES.keys())

    cleaned = [str(item).strip().lower() for item in sources if str(item).strip()]
    invalid = [item for item in cleaned if item not in _SUPPORTED_SOURCES]
    if invalid:
        raise DomainValidationError("Unsupported news source(s): " + ", ".join(sorted(set(invalid))))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _sanitize_item(item: ScrapedNewsItem) -> ScrapedNewsItem | None:
    title = re.sub(r"\s+", " ", (item.title or "")).strip()
    url = re.sub(r"\s+", "", (item.url or "")).strip()
    content = re.sub(r"\s+", " ", (item.content or "")).strip()
    source = (item.source or "").strip().lower()

    if not title or not url or len(content) < 120 or not source:
        return None

    published_at = item.published_at
    if published_at and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=INDIA_TZ)
    elif published_at:
        published_at = published_at.astimezone(INDIA_TZ)

    return ScrapedNewsItem(
        source=source,
        topic="latest",
        title=title,
        url=url,
        content=content,
        published_at=published_at,
    )


def _upsert_news_items(db: Session, items: list[ScrapedNewsItem]) -> int:
    saved_count = 0
    for item in items:
        stmt = insert(NewsArticle).values(
            source=item.source,
            topic="latest",
            title=item.title,
            url=item.url,
            content=item.content,
            language="english",
            published_at=item.published_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_news_articles_url",
            set_={
                "source": stmt.excluded.source,
                "topic": stmt.excluded.topic,
                "title": stmt.excluded.title,
                "content": stmt.excluded.content,
                "language": stmt.excluded.language,
                "published_at": stmt.excluded.published_at,
                "scraped_at": func.now(),
            },
        )
        db.execute(stmt)
        saved_count += 1

    db.commit()
    return saved_count


def _existing_urls_for_page(db: Session, urls: list[str]) -> set[str]:
    if not urls:
        return set()

    rows = db.execute(select(NewsArticle.url).where(NewsArticle.url.in_(urls))).scalars().all()
    return {str(item).strip().rstrip("/") for item in rows if item}


def _persist_page_items(db: Session, page_items: list[ScrapedNewsItem]) -> int:
    sanitized_rows: list[ScrapedNewsItem] = []
    for row in page_items:
        sanitized = _sanitize_item(row)
        if sanitized is not None:
            sanitized_rows.append(sanitized)

    if not sanitized_rows:
        return 0

    deduped_by_url: dict[str, ScrapedNewsItem] = {}
    for row in sanitized_rows:
        deduped_by_url[row.url] = row

    return _upsert_news_items(db, list(deduped_by_url.values()))


async def _run_source_scrape(
    source: str,
    db: Session,
    max_pages_per_source: int,
    keep_days: int,
    emit_log: Callable[[str], None] | None = None,
) -> tuple[str, list[ScrapedNewsItem], list[str]]:
    logs: list[str] = []
    scraper_fn = _SUPPORTED_SOURCES[source]
    resolver: ExistingUrlsResolver = lambda page_urls: _existing_urls_for_page(db, page_urls)

    def log(message: str) -> None:
        record_admin_log(logs, message, emit_log)

    log(f"{source}: starting latest-news scrape (max_pages={max_pages_per_source}, keep_days={keep_days})")

    page_number = 0

    def on_page_scraped(page_items: list[ScrapedNewsItem]) -> None:
        nonlocal page_number
        page_number += 1
        log(f"{source}: page {page_number} collected {len(page_items)} article(s)")

    try:
        if source == "indiatv":
            rows = await scraper_fn(
                include_days=keep_days,
                existing_urls_resolver=resolver,
                on_page_scraped=on_page_scraped,
            )
        else:
            rows = await scraper_fn(
                max_pages_per_source=max_pages_per_source,
                include_days=keep_days,
                existing_urls_resolver=resolver,
                on_page_scraped=on_page_scraped,
            )
    except Exception as exc:
        logger.exception("Latest-news scraper failed for source=%s", source)
        log(f"{source}: failed with {type(exc).__name__}: {exc}")
        return source, [], logs

    log(f"{source}: collected {len(rows)} article(s) ready for persistence")
    return source, rows, logs


async def run_news_latest_scraping(
    db: Session,
    sources: list[str] | None = None,
    max_pages_per_source: int = 12,
    keep_days: int = 3,
    emit_log: Callable[[str], None] | None = None,
) -> dict:
    resolved_sources = _resolve_sources(sources)
    keep_days = max(1, min(7, keep_days))
    max_pages_per_source = max(1, min(50, max_pages_per_source))

    by_source: dict[str, int] = {}
    total_scraped = 0
    total_saved = 0
    logs: list[str] = []

    def log(message: str) -> None:
        record_admin_log(logs, message, emit_log)

    log(f"Starting latest-news scrape for {', '.join(resolved_sources)} (max_pages={max_pages_per_source}, keep_days={keep_days})")

    tasks = [
        _run_source_scrape(
            source=source,
            db=db,
            max_pages_per_source=max_pages_per_source,
            keep_days=keep_days,
            emit_log=emit_log,
        )
        for source in resolved_sources
    ]
    results = await asyncio.gather(*tasks)

    for source, result in zip(resolved_sources, results):
        _, rows, source_logs = result
        logs.extend(source_logs)
        by_source[source] = len(rows)
        total_scraped += len(rows)
        saved_count = _persist_page_items(db, rows)
        total_saved += saved_count
        log(f"{source}: saved {saved_count} article(s)")

    log(f"Latest-news scrape complete: scraped {total_scraped} article(s), saved {total_saved} article(s)")

    return {
        "total_scraped": total_scraped,
        "total_saved": total_saved,
        "by_source": by_source,
        "sources": resolved_sources,
        "max_pages_per_source": max_pages_per_source,
        "keep_days": keep_days,
        "logs": logs,
    }
