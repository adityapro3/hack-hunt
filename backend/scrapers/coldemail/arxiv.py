import re
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

_ARXIV_RESULTS_PAGE_SIZE = 50
_ARXIV_SEARCH_BASE_URL = "https://arxiv.org/search/"
_DEFAULT_MAX_PUBLICATIONS = 100
_DEFAULT_MAX_PAGES = 15

logger = logging.getLogger(__name__)


@dataclass
class ResearchPublication:
    title: str
    year: int | None
    detail_url: str | None
    abstract: str | None


def _normalize_publication_title(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip(" .;")


def _normalize_professor_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def _parse_publication_year(raw: str | None) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None

    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None

    year = int(match.group(0))
    current_year = datetime.now(timezone.utc).year
    if year < 1950 or year > current_year + 1:
        return None
    return year


def _build_arxiv_author_search_url(professor_name: str, size: int) -> str:
    phrase_query = quote_plus(f'"{_normalize_professor_name(professor_name)}"')
    return (
        f"{_ARXIV_SEARCH_BASE_URL}?"
        f"query={phrase_query}&searchtype=author&abstracts=show"
        f"&order=-announced_date_first&size={size}"
    )


def _parse_arxiv_total_results(heading: str | None) -> int | None:
    text = (heading or "").strip()
    if not text:
        return None
    match = re.search(r"of\s+([\d,]+)\s+results", text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _clean_arxiv_abstract(text: str | None) -> str | None:
    value = _normalize_publication_title(text)
    if not value:
        return None
    value = re.sub(r"^abstract\s*:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[▽△]\s*(More|Less)\s*$", "", value, flags=re.IGNORECASE)
    value = _normalize_publication_title(value)
    if len(value) < 24:
        return None
    return value


def _extract_submitted_text_from_result(result_item: BeautifulSoup) -> str:
    submitted_text = ""
    for paragraph in result_item.select("p.is-size-7"):
        text = _normalize_publication_title(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        if "submitted" in text.lower():
            return text
        if not submitted_text:
            submitted_text = text
    return submitted_text


def _parse_arxiv_results_html(html: str) -> tuple[int | None, list[dict[str, str | None]]]:
    soup = BeautifulSoup(html, "html.parser")
    heading_node = soup.select_one("h1.title.is-clearfix") or soup.select_one("h1.title")
    total_results = _parse_arxiv_total_results(heading_node.get_text(" ", strip=True) if heading_node else None)

    rows: list[dict[str, str | None]] = []
    for item in soup.select("li.arxiv-result"):
        title = _normalize_publication_title(
            item.select_one("p.title").get_text(" ", strip=True) if item.select_one("p.title") else None
        )
        abstract_full = _normalize_publication_title(
            item.select_one("p.abstract span.abstract-full").get_text(" ", strip=True)
            if item.select_one("p.abstract span.abstract-full")
            else None
        )
        abstract_short = _normalize_publication_title(
            item.select_one("p.abstract span.abstract-short").get_text(" ", strip=True)
            if item.select_one("p.abstract span.abstract-short")
            else None
        )
        abstract_raw = abstract_full or abstract_short
        if not abstract_raw:
            abstract_raw = _normalize_publication_title(
                item.select_one("p.abstract").get_text(" ", strip=True) if item.select_one("p.abstract") else None
            )

        detail_url = None
        detail_anchor = item.select_one("p.list-title a[href*='/abs/']")
        if detail_anchor and detail_anchor.get("href"):
            detail_url = str(detail_anchor.get("href"))

        rows.append(
            {
                "title": title,
                "abstract": abstract_raw,
                "submitted_text": _extract_submitted_text_from_result(item),
                "detail_url": detail_url,
            }
        )

    return total_results, rows


def _append_publications_from_rows(
    rows: list[dict[str, str | None]],
    publications: list[ResearchPublication],
    seen_titles: set[str],
    max_publications: int,
) -> int:
    new_rows = 0
    for item in rows:
        title = _normalize_publication_title(item.get("title"))
        if len(title) < 8:
            continue

        key = title.casefold()
        if key in seen_titles:
            continue

        seen_titles.add(key)
        new_rows += 1
        publications.append(
            ResearchPublication(
                title=title,
                year=_parse_publication_year(item.get("submitted_text")),
                detail_url=item.get("detail_url") or None,
                abstract=_clean_arxiv_abstract(item.get("abstract")),
            )
        )

        if len(publications) >= max_publications:
            break

    return new_rows


async def _extract_arxiv_results_payload(page) -> tuple[int | None, list[dict[str, str | None]]]:
    payload = await page.evaluate(
        """() => {
            for (const link of document.querySelectorAll('li.arxiv-result p.abstract a.is-size-7')) {
                const label = (link.textContent || '').toLowerCase();
                if (label.includes('more')) {
                    link.click();
                }
            }

            const heading = (
                document.querySelector('h1.title.is-clearfix')?.textContent
                || document.querySelector('h1.title')?.textContent
                || ''
            ).replace(/\s+/g, ' ').trim();

            const results = [];
            for (const item of document.querySelectorAll('li.arxiv-result')) {
                const title = (
                    item.querySelector('p.title')?.textContent || ''
                ).replace(/\s+/g, ' ').trim();

                const abstractFull = (
                    item.querySelector('p.abstract span.abstract-full')?.textContent || ''
                ).replace(/\s+/g, ' ').trim();
                const abstractShort = (
                    item.querySelector('p.abstract span.abstract-short')?.textContent || ''
                ).replace(/\s+/g, ' ').trim();
                const abstractRaw = abstractFull || abstractShort || (
                    item.querySelector('p.abstract')?.textContent || ''
                ).replace(/\s+/g, ' ').trim();

                let submittedText = '';
                for (const p of item.querySelectorAll('p.is-size-7')) {
                    const text = (p.textContent || '').replace(/\s+/g, ' ').trim();
                    if (!text) {
                        continue;
                    }
                    if (text.toLowerCase().includes('submitted')) {
                        submittedText = text;
                        break;
                    }
                    if (!submittedText) {
                        submittedText = text;
                    }
                }

                const detailUrl = item.querySelector(\"p.list-title a[href*='/abs/']\")?.href || null;
                results.push({
                    title,
                    abstract: abstractRaw,
                    submitted_text: submittedText,
                    detail_url: detailUrl,
                });
            }

            return { heading, results };
        }"""
    )

    heading = payload.get("heading") if isinstance(payload, dict) else ""
    rows = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    return _parse_arxiv_total_results(heading), rows


async def fetch_arxiv_publications_playwright(
    professor_name: str,
    max_publications: int = _DEFAULT_MAX_PUBLICATIONS,
    page_step: int = _ARXIV_RESULTS_PAGE_SIZE,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> list[ResearchPublication]:
    normalized_name = _normalize_professor_name(professor_name)
    if not normalized_name:
        return []

    publications: list[ResearchPublication] = []
    seen_titles: set[str] = set()
    total_results: int | None = None
    current_size = page_step

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        try:
            for _ in range(max_pages):
                url = _build_arxiv_author_search_url(normalized_name, size=current_size)
                await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                await page.wait_for_selector("h1.title, li.arxiv-result", timeout=15_000)
                await page.wait_for_timeout(200)

                parsed_total, rows = await _extract_arxiv_results_payload(page)
                if total_results is None:
                    total_results = parsed_total

                if not rows:
                    break

                new_rows = _append_publications_from_rows(
                    rows=rows,
                    publications=publications,
                    seen_titles=seen_titles,
                    max_publications=max_publications,
                )

                if len(publications) >= max_publications:
                    break
                if total_results is not None and len(publications) >= min(total_results, max_publications):
                    break
                if total_results is not None and current_size >= total_results:
                    break
                if new_rows == 0:
                    break

                current_size += page_step
        finally:
            await browser.close()

    return publications


def fetch_arxiv_publications_requests(
    professor_name: str,
    max_publications: int = _DEFAULT_MAX_PUBLICATIONS,
    page_step: int = _ARXIV_RESULTS_PAGE_SIZE,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> list[ResearchPublication]:
    normalized_name = _normalize_professor_name(professor_name)
    if not normalized_name:
        return []

    publications: list[ResearchPublication] = []
    seen_titles: set[str] = set()
    total_results: int | None = None
    current_size = page_step

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )

    for _ in range(max_pages):
        url = _build_arxiv_author_search_url(normalized_name, size=current_size)
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("ArXiv requests+BS4 fetch failed for %s at size=%s: %s", normalized_name, current_size, exc)
            break

        parsed_total, rows = _parse_arxiv_results_html(response.text)
        if total_results is None:
            total_results = parsed_total

        if not rows:
            break

        new_rows = _append_publications_from_rows(
            rows=rows,
            publications=publications,
            seen_titles=seen_titles,
            max_publications=max_publications,
        )

        if len(publications) >= max_publications:
            break
        if total_results is not None and len(publications) >= min(total_results, max_publications):
            break
        if total_results is not None and current_size >= total_results:
            break
        if new_rows == 0:
            break

        current_size += page_step
        time.sleep(0.25)

    return publications
