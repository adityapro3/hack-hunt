import asyncio
import json
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date, sanitize_mode

logger = logging.getLogger(__name__)


class DevfolioScraper(BaseScraper):
    source = "devfolio"
    _url = "https://devfolio.co/hackathons"
    _max_items = 15
    _request_delay_seconds = 0.3
    _blocked_tokens = (
        "guide.devfolio.co",
        "status.devfolio.co",
        "blog.devfolio.co",
        "about.devfolio.co",
        "careers.devfolio.co",
        "changelog.devfolio.co",
        "code-of-conduct.devfolio.co",
        "brand-assets.devfolio.co",
        "privacy-policy.devfolio.co",
        "terms-of-use.devfolio.co",
        "discord.devfolio.co",
        "github.devfolio.co",
        "linkedin.devfolio.co",
        "twitter.devfolio.co",
        "dribbble.devfolio.co",
        "devfolio.co/hackathons",
        "devfolio.co/organize",
        "devfolio.co/discover",
        "devfolio.co/applied",
    )

    async def scrape(self) -> list[ScrapedOpportunity]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            response = await client.get(self._url, headers=headers)
            response.raise_for_status()

            event_urls = self._extract_event_urls(BeautifulSoup(response.text, "html.parser"))
            rows: list[ScrapedOpportunity] = []
            for event_url in event_urls[: self._max_items]:
                row = await self._scrape_event(client, event_url, headers)
                if row:
                    rows.append(row)
                await asyncio.sleep(self._request_delay_seconds)

        return rows

    def _extract_event_urls(self, soup: BeautifulSoup) -> list[str]:
        event_urls: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href.startswith("https://") or ".devfolio.co" not in href:
                continue

            normalized = href.split("?", maxsplit=1)[0].rstrip("/")
            if any(token in normalized for token in self._blocked_tokens):
                continue

            event_urls.add(normalized)

        return sorted(event_urls)

    async def _scrape_event(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
    ) -> ScrapedOpportunity | None:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Devfolio: failed to fetch %s (%s)", url, exc)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)
        hackathon: dict = {}

        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                payload = json.loads(script.string)
                hackathon = payload.get("props", {}).get("pageProps", {}).get("hackathon", {})
            except json.JSONDecodeError:
                logger.warning("Devfolio: invalid __NEXT_DATA__ payload for %s", url)

        title = (
            (hackathon.get("name") if isinstance(hackathon, dict) else "")
            or self._selector_text(soup, ["h1", "h2", "title"])
            or ""
        ).strip()
        if not title:
            return None

        if title.lower().endswith("| devfolio"):
            title = title.rsplit("|", maxsplit=1)[0].strip()

        settings = hackathon.get("settings", {}) if isinstance(hackathon, dict) else {}
        city = (hackathon.get("city") or "").strip() if isinstance(hackathon, dict) else ""
        country = (hackathon.get("country") or "").strip() if isinstance(hackathon, dict) else ""

        location = (
            (hackathon.get("location") or "").strip() if isinstance(hackathon, dict) else ""
        ) or " ".join([x for x in [city, country] if x])

        team_min = hackathon.get("team_min") if isinstance(hackathon, dict) else None
        team_max = hackathon.get("team_max") if isinstance(hackathon, dict) else None
        team_size = None
        if team_min is not None or team_max is not None:
            if team_min is not None and team_max is not None:
                team_size = f"{team_min}-{team_max}"
            else:
                team_size = str(team_min if team_min is not None else team_max)

        if not team_size:
            team_size = self._first_match(
                [
                    r"Team Size\s*:?\s*([^\n|]+)",
                    r"(\d+\s*(?:to|-)\s*\d+\s*members?)",
                    r"(Individuals?|Solo)",
                ],
                page_text,
            )

        prize_money = (
            (hackathon.get("prize_money") or "").strip() if isinstance(hackathon, dict) else ""
        ) or self._first_match(
            [
                r"Prize Pool\s*:?\s*([^\n|]+)",
                r"Total Prize\s*:?\s*([^\n|]+)",
                r"Prize Money\s*:?\s*([^\n|]+)",
                r"(₹\s*[\d,]+(?:\.\d+)?)",
                r"(\$\s*[\d,]+(?:\.\d+)?)",
            ],
            page_text,
        )

        deadline_text = (settings.get("reg_ends_at") if isinstance(settings, dict) else "") or self._first_match(
            [
                r"Registration\s*(?:Ends|Deadline|Close)\s*:?\s*([^\n|]+)",
                r"Last Date\s*:?\s*([^\n|]+)",
                r"Deadline\s*:?\s*([^\n|]+)",
            ],
            page_text,
        )

        start_date = parse_date(
            hackathon.get("starts_at") if isinstance(hackathon, dict) else None
        )
        end_date = parse_date(
            hackathon.get("ends_at") if isinstance(hackathon, dict) else None
        )
        deadline = parse_date(deadline_text)

        status = "active"
        if start_date:
            now = datetime.now(tz=start_date.tzinfo) if start_date.tzinfo else datetime.now()
            if start_date > now:
                status = "upcoming"

        is_online = hackathon.get("is_online") if isinstance(hackathon, dict) else None
        mode_token = None
        if is_online is True:
            mode_token = "online"
        elif is_online is False:
            mode_token = "offline"
        else:
            mode_token = self._first_match([r"\b(online|offline|hybrid)\b"], page_text)

        themes = []
        if isinstance(hackathon, dict):
            themes = [
                item.get("theme", {}).get("name", "")
                for item in hackathon.get("themes", [])
                if isinstance(item, dict)
            ]

        registration_fee = None
        text_l = page_text.lower()
        if "free" in text_l:
            registration_fee = "free"
        elif "paid" in text_l or "registration fee" in text_l:
            registration_fee = "paid"

        detail_url = settings.get("site") if isinstance(settings, dict) else None
        if not detail_url or not isinstance(detail_url, str):
            detail_url = url

        return ScrapedOpportunity(
            opportunity_type="hackathon",
            title=title,
            url=detail_url,
            source=self.source,
            description=(hackathon.get("desc") if isinstance(hackathon, dict) else "")
            or self._selector_text(
                soup,
                [
                    ".about",
                    ".description",
                    ".event-description",
                    "[class*='desc']",
                    ".content",
                ],
            )
            or None,
            domains=dedupe_text_list([x for x in themes if x]),
            skills=[],
            mode=sanitize_mode(mode_token),
            location=location or None,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            prize_money=prize_money or None,
            registration_fee=registration_fee,
            team_size=team_size,
            eligibility=[],
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
            cleaned = value.strip()
            if cleaned:
                return cleaned
        return None