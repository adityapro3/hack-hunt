import re
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.news.common import (
    ExistingUrlsResolver,
    PageItemsCallback,
    canonical_link,
    extract_newsarticle_date_from_ldjson,
    fetch_html,
    normalize_space,
    parse_datetime,
    scrape_paginated_latest,
)
from backend.scrapers.base import ScrapedNewsItem


def _news18_page_url(page_number: int) -> str:
    if page_number <= 1:
        return "https://www.news18.com/news/"
    return f"https://www.news18.com/news/page-{page_number}/"


def _extract_news18_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = f"https://www.news18.com{href}"

        parsed = urlparse(href)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()

        if "news18.com" not in host:
            continue
        if not path or path in {"/", "/news/"}:
            continue
        if not path.endswith(".html"):
            continue
        if not re.search(r"-\d+\.html$", path):
            continue
        if any(token in path for token in ("/photos/", "/videos/", "/web-stories/", "/livetv/")):
            continue

        normalized_href = href
        if host != "www.news18.com":
            normalized_href = urlunparse(parsed._replace(netloc="www.news18.com"))

        links.append(canonical_link(normalized_href))

    return list(dict.fromkeys(links))


async def _parse_news18_article(client: httpx.AsyncClient, url: str) -> ScrapedNewsItem | None:
    html = await fetch_html(client, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find("h2", id=lambda token: isinstance(token, str) and token.startswith("asubttl"))
    if title_node is None:
        title_node = soup.find("h1")
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None

    meta_published = soup.select_one("meta[property='article:published_time'][content]")
    published_at = parse_datetime(meta_published.get("content") if meta_published else None)
    if published_at is None:
        time_node = soup.find("time")
        published_at = parse_datetime(
            (time_node.get("datetime") if time_node else None)
            or (time_node.get_text(" ", strip=True) if time_node else None)
        )

    date_node = soup.find("ul", class_="fp")
    if published_at is None:
        published_at = parse_datetime(date_node.get_text(" ", strip=True) if date_node else None)
    if published_at is None:
        published_at = extract_newsarticle_date_from_ldjson(soup)

    paragraphs = soup.find_all("p", class_=lambda token: isinstance(token, str) and token.startswith("story_para_"))
    if not paragraphs:
        paragraphs = soup.select("article p")
    if not paragraphs:
        paragraphs = soup.select("div.livebox p, div.lbgcontent p")

    content = normalize_space(" ".join(node.get_text(" ", strip=True) for node in paragraphs))
    if len(content) < 120:
        return None

    return ScrapedNewsItem(
        source="news18",
        topic="latest",
        title=title,
        url=url,
        content=content,
        published_at=published_at,
    )


async def scrape_news18_latest(
    max_pages_per_source: int = 12,
    include_days: int = 3,
    existing_urls_resolver: ExistingUrlsResolver | None = None,
    on_page_scraped: PageItemsCallback | None = None,
) -> list[ScrapedNewsItem]:
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=25, headers=headers, follow_redirects=True) as client:
        return await scrape_paginated_latest(
            client=client,
            source_name="news18",
            build_page_url=_news18_page_url,
            extract_links=_extract_news18_links,
            parse_article=_parse_news18_article,
            max_pages_per_source=max_pages_per_source,
            include_days=include_days,
            existing_urls_resolver=existing_urls_resolver,
            on_page_scraped=on_page_scraped,
        )
