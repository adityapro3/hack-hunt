import httpx
from bs4 import BeautifulSoup

from backend.scrapers.news.common import (
    ExistingUrlsResolver,
    PageItemsCallback,
    canonical_link,
    fetch_html,
    normalize_space,
    parse_datetime,
    scrape_paginated_latest,
)
from backend.scrapers.base import ScrapedNewsItem

def _indianexpress_page_url(page_number: int) -> str:
    if page_number <= 1:
        return "https://indianexpress.com/latest-news/"
    return f"https://indianexpress.com/latest-news/page/{page_number}/"


def _extract_indianexpress_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select("div.nation a[href], .articles a[href], article a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        if "indianexpress.com" not in href:
            continue
        if "/latest-news/" in href:
            continue
        if "/photos/" in href or "/videos/" in href:
            continue
        links.append(canonical_link(href))
    return list(dict.fromkeys(links))


async def _parse_indianexpress_article(client: httpx.AsyncClient, url: str) -> ScrapedNewsItem | None:
    html = await fetch_html(client, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("h1[itemprop='headline']") or soup.select_one("h1.article-main-head")
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None

    date_node = soup.select_one("span[itemprop='dateModified']")
    published_at = parse_datetime(date_node.get("content") if date_node else None)

    content_root = soup.select_one("div#pcl-full-content")
    paragraphs = content_root.select("p") if content_root else []
    content = normalize_space(" ".join(p.get_text(" ", strip=True) for p in paragraphs))
    if len(content) < 120:
        return None

    return ScrapedNewsItem(
        source="indianexpress",
        topic="latest",
        title=title,
        url=url,
        content=content,
        published_at=published_at,
    )


async def scrape_indianexpress_latest(
    max_pages_per_source: int = 12,
    include_days: int = 3,
    existing_urls_resolver: ExistingUrlsResolver | None = None,
    on_page_scraped: PageItemsCallback | None = None,
) -> list[ScrapedNewsItem]:
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=25, headers=headers, follow_redirects=True) as client:
        return await scrape_paginated_latest(
            client=client,
            source_name="indianexpress",
            build_page_url=_indianexpress_page_url,
            extract_links=_extract_indianexpress_links,
            parse_article=_parse_indianexpress_article,
            max_pages_per_source=max_pages_per_source,
            include_days=include_days,
            existing_urls_resolver=existing_urls_resolver,
            on_page_scraped=on_page_scraped,
        )
