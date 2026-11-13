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


def _livemint_page_url(page_number: int) -> str:
    if page_number <= 1:
        return "https://www.livemint.com/latest-news"
    return f"https://www.livemint.com/latest-news/page-{page_number}"


def _extract_livemint_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select(".listingNew h2.headline a[href], h2.headline a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = f"https://www.livemint.com{href}"
        if "livemint.com" not in href:
            continue
        links.append(canonical_link(href))
    return list(dict.fromkeys(links))


async def _parse_livemint_article(client: httpx.AsyncClient, url: str) -> ScrapedNewsItem | None:
    html = await fetch_html(client, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find("h1", id="article-0") or soup.find("h1", class_="headline")
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None

    date_node = soup.find("div", class_=lambda token: isinstance(token, str) and token.startswith("storyPage_date"))
    if date_node is None:
        date_node = soup.find("span", class_="articleInfo pubtime fl")
    published_at = parse_datetime(date_node.get_text(" ", strip=True) if date_node else None)
    if published_at is None:
        meta_published = soup.select_one("meta[property='article:published_time'][content]")
        published_at = parse_datetime(meta_published.get("content") if meta_published else None)
    if published_at is None:
        published_at = extract_newsarticle_date_from_ldjson(soup)

    story_nodes = soup.find_all(
        "div",
        class_=lambda token: isinstance(token, str) and (token == "storyParagraph" or token == "liveSecIntro"),
    )
    content = normalize_space(" ".join(node.get_text(" ", strip=True) for node in story_nodes))
    if len(content) < 120:
        return None

    return ScrapedNewsItem(
        source="livemint",
        topic="latest",
        title=title,
        url=url,
        content=content,
        published_at=published_at,
    )


async def scrape_livemint_latest(
    max_pages_per_source: int = 12,
    include_days: int = 3,
    existing_urls_resolver: ExistingUrlsResolver | None = None,
    on_page_scraped: PageItemsCallback | None = None,
) -> list[ScrapedNewsItem]:
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=25, headers=headers, follow_redirects=True) as client:
        return await scrape_paginated_latest(
            client=client,
            source_name="livemint",
            build_page_url=_livemint_page_url,
            extract_links=_extract_livemint_links,
            parse_article=_parse_livemint_article,
            max_pages_per_source=max_pages_per_source,
            include_days=include_days,
            existing_urls_resolver=existing_urls_resolver,
            on_page_scraped=on_page_scraped,
        )
