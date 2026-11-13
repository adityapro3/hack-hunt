import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date, sanitize_mode

logger = logging.getLogger(__name__)


class HackerearthScraper(BaseScraper):
    source = "hackerearth"
    _url = "https://www.hackerearth.com/challenges/?filters=hackathon"
    _max_items = 15
    _request_delay_seconds = 0.35

    async def scrape(self) -> list[ScrapedOpportunity]:
        challenge_refs: list[tuple[str, str]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            )

            try:
                await page.goto(self._url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)
                soup = BeautifulSoup(await page.content(), "html.parser")

                for selector, status in (
                    ("div.ongoing.challenge-list", "active"),
                    ("div.upcoming.challenge-list", "upcoming"),
                ):
                    container = soup.select_one(selector)
                    if not container:
                        continue
                    for card in container.select("a.challenge-card-wrapper, a.challenge-card-wrapper.challenge-card-link"):
                        href = card.get("href")
                        if not href:
                            continue
                        if href.startswith("/"):
                            href = f"https://www.hackerearth.com{href}"
                        challenge_refs.append((href, status))

                if not challenge_refs:
                    for card in soup.select("a.challenge-card-wrapper"):
                        href = card.get("href")
                        if not href:
                            continue
                        if href.startswith("/"):
                            href = f"https://www.hackerearth.com{href}"
                        challenge_refs.append((href, "active"))
            except Exception as exc:
                logger.warning("HackerEarth: listing scrape failed (%s)", exc)
            finally:
                await browser.close()

        deduped: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for url, status in challenge_refs:
            normalized = url.split("?", maxsplit=1)[0]
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            deduped.append((normalized, status))

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        selected = deduped[: self._max_items]

        scraped: list[ScrapedOpportunity | None] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for index, (url, status) in enumerate(selected):
                scraped.append(
                    await self._scrape_challenge(client=client, url=url, status=status, headers=headers)
                )
                if index < len(selected) - 1:
                    await asyncio.sleep(self._request_delay_seconds)

        return [item for item in scraped if item]

    async def _scrape_challenge(
        self,
        client: httpx.AsyncClient,
        url: str,
        status: str,
        headers: dict[str, str],
    ) -> ScrapedOpportunity | None:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("HackerEarth: failed to fetch %s (%s)", url, exc)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)

        title = self._selector_text(
            soup,
            [
                "h1.challenge-title",
                "h1.header-title",
                ".challenge-header h1",
                "h1",
                "title",
            ],
        )
        if not title:
            return None
        if title.lower().endswith("| hackerearth"):
            title = title.rsplit("|", maxsplit=1)[0].strip()

        mode_text = self._selector_text(soup, ["div.regular.bold.desc.dark"])
        if not mode_text:
            mode_text = self._first_match([r"\b(online|offline|onsite|in-person|hybrid)\b"], page_text)

        description = self._selector_text(
            soup,
            [
                ".description",
                ".challenge-description",
                ".about-challenge",
                ".content",
                "[class*='desc']",
            ],
        )
        if description and len(description) > 1000:
            description = description[:1000]

        deadline_text = self._first_match(
            [
                r"(?:Registration|Submission)\s*(?:Ends|Deadline)\s*:?\s*([^\n|]+)",
                r"Deadline\s*:?\s*([^\n|]+)",
            ],
            page_text,
        )

        date_matches: list[str] = []
        for pattern in (
            r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",
            r"\d{4}[/-]\d{1,2}[/-]\d{1,2}",
            r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}",
        ):
            date_matches.extend(re.findall(pattern, page_text, re.IGNORECASE))

        parsed_dates = [parse_date(value) for value in dict.fromkeys(date_matches)]
        parsed_dates = [value for value in parsed_dates if value]

        start_date = parsed_dates[0] if parsed_dates else None
        end_date = parsed_dates[1] if len(parsed_dates) > 1 else None
        deadline = parse_date(deadline_text) or (parsed_dates[-1] if parsed_dates else None)

        registration_fee = None
        page_text_l = page_text.lower()
        if re.search(r"\b(free|no cost|no fee)\b", page_text_l):
            registration_fee = "free"
        elif re.search(r"\b(paid|registration fee)\b", page_text_l):
            registration_fee = "paid"

        team_size = self._first_match(
            [
                r"Team Size\s*:?\s*(\d+\s*(?:to|-)\s*\d+|\d+\s*members?)",
                r"(Individuals?|Solo)",
            ],
            page_text,
        )

        prize_money = self._first_match(
            [
                r"Prize\s*:?\s*([^\n|]+)",
                r"(₹\s*[\d,]+|\$\s*[\d,]+)",
            ],
            page_text,
        )

        location = self._selector_text(soup, [".location", ".venue", ".place", "[class*='location']"])

        eligibility = [
            node.get_text(separator=" ", strip=True)
            for node in soup.select(".eligibility, [class*='eligi'], .requirements")
        ]
        domains = [
            node.get_text(separator=" ", strip=True)
            for node in soup.select(".category, .tag, .badge, [class*='tag'], [class*='category']")
        ]

        return ScrapedOpportunity(
            opportunity_type="hackathon",
            title=title,
            url=url,
            source=self.source,
            description=description or None,
            domains=dedupe_text_list(domains),
            skills=[],
            mode=sanitize_mode(mode_text),
            location=location or None,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            prize_money=prize_money or None,
            registration_fee=registration_fee,
            team_size=team_size,
            eligibility=dedupe_text_list(eligibility),
            status=status,
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