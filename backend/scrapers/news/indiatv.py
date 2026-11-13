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


def _indiatv_page_url(_page_number: int) -> str:
    return "https://www.indiatvnews.com/latest-news"


def _extract_indiatv_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select("div.box a[href], article a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        if "indiatvnews.com" not in href:
            continue
        if "/videos/" in href:
            continue
        links.append(canonical_link(href))
    return list(dict.fromkeys(links))


async def _parse_indiatv_article(client: httpx.AsyncClient, url: str) -> ScrapedNewsItem | None:
    html = await fetch_html(client, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find("h1", class_="arttitle")
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None

    time_node = soup.find("time")
    published_at = parse_datetime(time_node.get("datetime") if time_node else None)

    content_root = soup.find("div", class_="content", id="content")
    paragraphs = content_root.find_all("p") if content_root else []
    content = normalize_space(" ".join(node.get_text(" ", strip=True) for node in paragraphs))
    if len(content) < 120:
        return None

    return ScrapedNewsItem(
        source="indiatv",
        topic="latest",
        title=title,
        url=url,
        content=content,
        published_at=published_at,
    )


async def scrape_indiatv_latest(
    include_days: int = 3,
    existing_urls_resolver: ExistingUrlsResolver | None = None,
    on_page_scraped: PageItemsCallback | None = None,
) -> list[ScrapedNewsItem]:
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=25, headers=headers, follow_redirects=True) as client:
        return await scrape_paginated_latest(
            client=client,
            source_name="indiatv",
            build_page_url=_indiatv_page_url,
            extract_links=_extract_indiatv_links,
            parse_article=_parse_indiatv_article,
            max_pages_per_source=1,
            include_days=include_days,
            existing_urls_resolver=existing_urls_resolver,
            on_page_scraped=on_page_scraped,
        )
