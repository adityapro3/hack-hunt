import asyncio
import json
import logging
import re
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from backend.scrapers.base import ScrapedNewsItem

logger = logging.getLogger(__name__)
INDIA_TZ = ZoneInfo("Asia/Kolkata")

# Suppress noisy logs from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ExistingUrlsResolver = Callable[[list[str]], set[str]]
PageItemsCallback = Callable[[list[ScrapedNewsItem]], None]
BuildPageUrlFn = Callable[[int], str]
ExtractLinksFn = Callable[[str], list[str]]
ParseArticleFn = Callable[[httpx.AsyncClient, str], Awaitable[ScrapedNewsItem | None]]
NEWS_CONTENT_MAX_CHARS = 12_500
NEWS_ARTICLE_DELAY_SECONDS = 0.2
NEWS_PAGE_DELAY_SECONDS = 0.35


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_datetime(raw: str | None) -> datetime | None:
    text = normalize_space(raw)
    if not text:
        return None

    cleaned = (
        text.replace("First Published:", "")
        .replace("Updated", "")
        .replace("Published", "")
        .strip(" ,")
    )
    cleaned = re.sub(r"\bIST\b", "+05:30", cleaned)
    try:
        parsed = date_parser.parse(cleaned, fuzzy=True)
    except Exception:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=INDIA_TZ)
    return parsed.astimezone(INDIA_TZ)


def canonical_link(link: str) -> str:
    return normalize_space(link).rstrip("/")


def truncate_news_content(content: str | None) -> str:
    normalized = normalize_space(content)
    if len(normalized) <= NEWS_CONTENT_MAX_CHARS:
        return normalized
    return normalized[:NEWS_CONTENT_MAX_CHARS].rstrip()


def extract_newsarticle_date_from_ldjson(soup: BeautifulSoup) -> datetime | None:
    for script in soup.select("script[type='application/ld+json']"):
        raw = (script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("@type") or "")
            if "NewsArticle" not in node_type:
                continue

            for key in ("datePublished", "dateModified"):
                value = node.get(key)
                parsed = parse_datetime(str(value) if value else None)
                if parsed is not None:
                    return parsed
    return None


def should_keep_article(published_at: datetime | None, include_from_date: date, include_to_date: date) -> bool:
    if not published_at:
        return False
    day = published_at.astimezone(INDIA_TZ).date()
    return include_from_date <= day <= include_to_date


def should_stop_pagination(published_at: datetime | None, stop_on_or_before_date: date) -> bool:
    if not published_at:
        return False
    day = published_at.astimezone(INDIA_TZ).date()
    return day <= stop_on_or_before_date


async def fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
        if response.status_code != 200:
            logger.warning("Failed fetching %s (status=%s)", url, response.status_code)
            return None
        return response.text
    except Exception as exc:
        logger.warning("Request failed for %s: %s", url, exc)
        return None


async def scrape_paginated_latest(
    *,
    client: httpx.AsyncClient,
    source_name: str,
    build_page_url: BuildPageUrlFn,
    extract_links: ExtractLinksFn,
    parse_article: ParseArticleFn,
    max_pages_per_source: int,
    include_days: int,
    existing_urls_resolver: ExistingUrlsResolver | None = None,
    on_page_scraped: PageItemsCallback | None = None,
) -> list[ScrapedNewsItem]:
    today = datetime.now(INDIA_TZ).date()
    include_from_date = today - timedelta(days=max(0, include_days - 1))
    include_to_date = today
    stop_on_or_before_date = today - timedelta(days=include_days)

    collected: list[ScrapedNewsItem] = []
    seen_links: set[str] = set()

    for page_number in range(1, max_pages_per_source + 1):
        page_url = build_page_url(page_number)
        page_html = await fetch_html(client, page_url)
        if not page_html:
            continue

        raw_links = extract_links(page_html)
        if not raw_links:
            logger.info("No links found for source=%s page=%s", source_name, page_number)
            continue

        page_links: list[str] = []
        for link in raw_links:
            canonical = canonical_link(link)
            if not canonical or canonical in seen_links:
                continue
            seen_links.add(canonical)
            page_links.append(canonical)

        if not page_links:
            continue

        existing_urls: set[str] = set()
        if existing_urls_resolver is not None:
            try:
                existing_urls = {canonical_link(url) for url in existing_urls_resolver(page_links)}
            except Exception as exc:
                logger.warning(
                    "Existing URL resolver failed for source=%s page=%s: %s",
                    source_name,
                    page_number,
                    exc,
                )

        reached_cutoff = False
        page_collected: list[ScrapedNewsItem] = []

        for link in page_links:
            if link in existing_urls:
                continue

            article = await parse_article(client, link)
            await asyncio.sleep(NEWS_ARTICLE_DELAY_SECONDS)
            if article is None:
                continue

            article.content = truncate_news_content(article.content)

            if should_stop_pagination(article.published_at, stop_on_or_before_date):
                reached_cutoff = True
                logger.info(
                    "Stopping source=%s at page=%s due to cutoff date article (%s)",
                    source_name,
                    page_number,
                    article.published_at,
                )
                break

            if should_keep_article(article.published_at, include_from_date, include_to_date):
                page_collected.append(article)

        if page_collected:
            if on_page_scraped is not None:
                try:
                    on_page_scraped(page_collected)
                except Exception:
                    logger.exception("Persist callback failed for source=%s page=%s", source_name, page_number)
            collected.extend(page_collected)

        if reached_cutoff:
            break

        await asyncio.sleep(NEWS_PAGE_DELAY_SECONDS)

    logger.info(
        "Latest news scrape completed for source=%s collected=%s include_from=%s include_to=%s",
        source_name,
        len(collected),
        include_from_date,
        include_to_date,
    )
    return collected
