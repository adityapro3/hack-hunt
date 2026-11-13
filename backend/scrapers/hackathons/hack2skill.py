import asyncio
import logging
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date, sanitize_mode

logger = logging.getLogger(__name__)


class Hack2skillScraper(BaseScraper):
    source = "hack2skill"
    _url = "https://vision.hack2skill.com/hackathons-listing?utm_source=hack2skill&utm_medium=homepage"
    _max_items = 15

    async def scrape(self) -> list[ScrapedOpportunity]:
        rows: list[ScrapedOpportunity] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            try:
                await page.goto(self._url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(1.5)

                for _ in range(3):
                    await page.evaluate("if (document.body) { window.scrollBy(0, document.body.scrollHeight); }")
                    await asyncio.sleep(1)

                accept_button = await page.query_selector('button:has-text("Accept")')
                if accept_button:
                    await accept_button.click()
                    await asyncio.sleep(0.4)

                links = await page.query_selector_all("a[href*='/event/']")
                event_urls: list[str] = []
                seen: set[str] = set()

                for anchor in links:
                    href = await anchor.get_attribute("href")
                    if not href:
                        continue

                    if href.startswith("/event/"):
                        href = f"https://vision.hack2skill.com{href}"

                    if "vision.hack2skill.com/event/" not in href:
                        continue

                    normalized = href.split("?", maxsplit=1)[0]
                    if normalized in seen:
                        continue

                    seen.add(normalized)
                    event_urls.append(normalized)
                    if len(event_urls) >= self._max_items:
                        break

                for url in event_urls[: self._max_items]:
                    item = await self._scrape_hackathon_details(page, url)
                    if item:
                        rows.append(item)
                    await asyncio.sleep(0.2)
            except Exception as exc:
                logger.warning("Hack2Skill: listing scrape failed (%s)", exc)
            finally:
                await browser.close()

        return rows

    async def _scrape_hackathon_details(self, page, url: str) -> ScrapedOpportunity | None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(0.8)
        except Exception as exc:
            logger.warning("Hack2Skill: failed loading %s (%s)", url, exc)
            return None

        html = None
        for _ in range(2):
            try:
                html = await page.content()
                break
            except Exception:
                await asyncio.sleep(0.6)
        if not html:
            logger.warning("Hack2Skill: failed reading content %s", url)
            return None

        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)

        title = self._selector_text(soup, ["h1", "h2", ".event-title", ".title", ".main-title", "title"])
        if title and title.lower().endswith("| hack2skill"):
            title = title.rsplit("|", maxsplit=1)[0].strip()

        if not title:
            fallback = soup.find(["div", "span"], string=re.compile(r"\w+ Hackathon", re.IGNORECASE))
            if fallback:
                title = fallback.get_text(separator=" ", strip=True)

        if not title:
            return None

        description = None
        for selector in [
            ".description",
            ".event-description",
            "[class*='desc']",
            ".about",
            ".detail-text",
            ".content",
            ".live-edit-event-page-about-section",
            ".why-join-wrapper",
            ".why-join-container",
        ]:
            node = soup.select_one(selector)
            if not node:
                continue
            text = node.get_text(separator=" ", strip=True)
            if len(text) > 50:
                description = text[:1200]
                break

        if not description:
            paragraphs = soup.select("p")
            for paragraph in paragraphs[:6]:
                text = paragraph.get_text(separator=" ", strip=True)
                if len(text) > 80 and "hackathon" in text.lower():
                    description = text[:1000]
                    break
            if not description and paragraphs:
                description = paragraphs[0].get_text(separator=" ", strip=True)[:1000]

        location = self._selector_text(
            soup,
            [".location", ".venue", ".place", ".address", ".city", ".event-location"],
        )

        deadline_text = self._first_match(
            [
                r"(?:LAST DATE TO|Registration.*?Deadline|Registrations (?:Ends|End).*?On)\s*:?\s*([^\n|]+)",
                r"(?:Last Date to Register|Deadline|Register by|Registrations Close|Registration closes|Last Date)\s*[:\-]?\s*([^\n|]+)",
            ],
            page_text,
        )
        start_text = self._first_match(
            [r"(?:Start|Event Starts|Hackathon Starts|Begins|Starts on?)\s*:?\s*([^\n|]+)"],
            page_text,
        )
        end_text = self._first_match(
            [r"(?:End|Event Ends|Hackathon Ends|Ends on?)\s*:?\s*([^\n|]+)"],
            page_text,
        )

        prize_money = self._first_match(
            [
                r"(?:Prize Pool|Prizes worth|Rewards|Total Prize|Prize Money)\s*[:\-]?\s*([^\n|]+)",
                r"(₹\s*[\d,]+|Rs\.?\s*[\d,]+|\$\s*[\d,]+)",
            ],
            page_text,
        )
        team_size = self._first_match([r"Team Size\s*:?\s*([^\n|]+)"], page_text)

        registration_fee = None
        fee_text = self._first_match([r"Registration Fee\s*:?\s*([^\n|]+)"], page_text)
        if fee_text:
            registration_fee = fee_text[:100].lower()
        elif re.search(r"\bfree\b", page_text, re.IGNORECASE):
            registration_fee = "free"
        elif re.search(r"\b(?:paid|rupees?|₹)\b", page_text, re.IGNORECASE):
            registration_fee = "paid"

        mode = None
        page_text_l = page_text.lower()
        if "hybrid" in page_text_l:
            mode = "hybrid"
        elif "online" in page_text_l:
            mode = "online"
        elif "in person" in page_text_l or "in-person" in page_text_l or "in-house" in page_text_l:
            mode = "offline"

        domains = []
        for selector in [".tag", ".category", "[class*='tag']", "[class*='category']", ".badge", ".chip"]:
            for node in soup.select(selector):
                text = node.get_text(separator=" ", strip=True)
                if text and 2 < len(text) < 100:
                    domains.append(text)

        eligibility = []
        for selector in [".eligibility", "[class*='eligi']", ".requirements", ".criteria", ".event-details__item"]:
            for node in soup.select(selector):
                text = node.get_text(separator=" ", strip=True)
                if text and len(text) > 3 and "elig" in text.lower():
                    eligibility.append(text)

        return ScrapedOpportunity(
            opportunity_type="hackathon",
            title=title,
            url=url,
            source=self.source,
            description=description or None,
            domains=dedupe_text_list(domains),
            skills=[],
            mode=sanitize_mode(mode),
            location=location or None,
            start_date=parse_date(start_text),
            end_date=parse_date(end_text),
            deadline=parse_date(deadline_text),
            prize_money=prize_money or None,
            registration_fee=registration_fee,
            team_size=team_size,
            eligibility=dedupe_text_list(eligibility),
            status="active",
        )

    @staticmethod
    def _selector_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            node = soup.select_one(selector)
            if not node:
                continue
            text = node.get_text(separator=" ", strip=True)
            if text:
                return text
        return None

    @staticmethod
    def _first_match(patterns: list[str], text: str) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip()
            if value:
                return value
        return None