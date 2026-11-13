import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date

logger = logging.getLogger(__name__)


class NeurIPSScraper(BaseScraper):
    source = "neurips"
    _url = "https://neurips.cc/virtual/2024/events/competition"
    _base_url = "https://neurips.cc"
    _max_items = 20
    _max_retries = 3
    _retry_delay = 2

    async def scrape(self) -> list[ScrapedOpportunity]:
        """Scrape NeurIPS competitions with retry logic."""
        rows: list[ScrapedOpportunity] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            event_urls = await self._extract_event_urls(client, headers)
            
            for event_url in event_urls[: self._max_items]:
                row = await self._scrape_event_with_retry(client, event_url, headers)
                if row:
                    rows.append(row)
                    await asyncio.sleep(0.5)

        return rows

    async def _extract_event_urls(self, client: httpx.AsyncClient, headers: dict) -> list[str]:
        """Extract competition URLs from the main events page."""
        event_urls: list[str] = []
        
        for attempt in range(self._max_retries):
            try:
                response = await client.get(self._url, headers=headers, timeout=45)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for competition links
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "").strip()
                    # Look for competition detail pages
                    if "/competition/" in href or "/track/" in href:
                        full_url = href if href.startswith("http") else f"{self._base_url}{href}"
                        full_url = full_url.split("?", maxsplit=1)[0].rstrip("/")
                        if full_url not in event_urls and self._base_url in full_url:
                            event_urls.append(full_url)
                
                if event_urls:
                    logger.info(f"NeurIPS: Found {len(event_urls)} competition URLs")
                    return event_urls
                    
            except Exception as exc:
                logger.warning(f"NeurIPS: attempt {attempt + 1} to extract URLs failed: {exc}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)
        
        return event_urls

    async def _scrape_event_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
    ) -> ScrapedOpportunity | None:
        """Scrape event with retry logic for resilience."""
        for attempt in range(self._max_retries):
            try:
                result = await self._scrape_event(client, url, headers)
                if result and result.title:
                    # Ensure we got at least some key fields
                    return result
                elif result:
                    logger.debug(f"NeurIPS: got partial result for {url}, retrying...")
            except Exception as exc:
                logger.debug(f"NeurIPS: attempt {attempt + 1} for {url} failed: {exc}")
            
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)
        
        return None

    async def _scrape_event(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
    ) -> ScrapedOpportunity | None:
        """Scrape a single NeurIPS competition page."""
        try:
            response = await client.get(url, headers=headers, timeout=45)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"NeurIPS: failed to fetch {url}: {exc}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)

        # Extract title
        title = self._extract_title(soup, page_text)
        if not title:
            return None

        # Extract all required and optional fields
        description = self._extract_description(soup, page_text)
        location = self._extract_location(soup, page_text)
        mode = self._extract_mode(soup, page_text, location)
        start_date, end_date = self._extract_dates(soup, page_text)
        deadline = self._extract_deadline(soup, page_text)
        prize_money = self._extract_prize_money(soup, page_text)
        team_size = self._extract_team_size(soup, page_text)
        domains = self._extract_domains(soup, page_text)
        registration_fee = self._extract_registration_fee(soup, page_text)
        status = self._extract_status(soup, page_text)
        eligibility = self._extract_eligibility(soup, page_text)

        return ScrapedOpportunity(
            opportunity_type="hackathon",
            title=title,
            url=url,
            source=self.source,
            description=description,
            domains=dedupe_text_list(domains),
            skills=[],
            mode=mode,
            location=location,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            prize_money=prize_money,
            registration_fee=registration_fee,
            team_size=team_size,
            eligibility=eligibility,
            status=status,
        )

    def _extract_title(self, soup: BeautifulSoup, page_text: str) -> str:
        """Extract competition title."""
        # Try multiple selectors for title
        for selector in ["h1", "h2", "[class*='title']", "[class*='heading']"]:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 5:
                    return text[:200]
        
        # Fallback: extract from page text
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        for line in lines[:5]:
            if len(line) > 10 and len(line) < 200:
                return line
        
        return ""

    def _extract_description(self, soup: BeautifulSoup, page_text: str) -> str | None:
        """Extract competition description."""
        description_parts = []

        # Look for main content area with description
        main_content = soup.find(id=re.compile(r"main|content", re.I))
        if not main_content:
            main_content = soup.find("main") or soup.find("article")
        
        if main_content:
            # Get all paragraphs from main content
            paragraphs = main_content.find_all("p", limit=10)
            for p in paragraphs:
                text = p.get_text(separator=" ", strip=True)
                # Filter out navigation, header, and UI text
                if (
                    len(text) > 80
                    and len(text) < 5000
                    and not any(
                        skip in text.lower()
                        for skip in [
                            "select year",
                            "button",
                            "click here",
                            "register",
                            "submit",
                            "javascript",
                        ]
                    )
                ):
                    description_parts.append(text)

        if description_parts:
            # Combine and limit
            combined = " ".join(description_parts[:3])[:1500]
            return combined if combined else None

        # Fallback: extract from page text between title and dates
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            if len(line.strip()) > 100 and len(line.strip()) < 500:
                return line.strip()[:1500]

        return None

    def _extract_location(self, soup: BeautifulSoup, page_text: str) -> str | None:
        """Extract location information."""
        page_text_lower = page_text.lower()

        # Check for virtual/online
        if any(
            term in page_text_lower
            for term in ["virtual only", "virtual event", "online event", "virtual", "remote"]
        ):
            return "Virtual"

        # Look for specific location patterns
        location_patterns = [
            r"Location\s*:?\s*([^\n|]+?)(?:\n|$|at|,|\||;)",
            r"Venue\s*:?\s*([^\n|]+?)(?:\n|$|,|\||;)",
            r"(?:held at|location is|venue:)\s*([^\n|]+?)(?:\n|,|$)",
            r"(?:San Francisco|New York|Boston|London|Singapore|Tokyo|Paris|Berlin|Toronto|Vancouver|Montreal)(?:\s+[A-Z]{2})?",
        ]

        for pattern in location_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                location = match.group(1) if "Location" in pattern or "Venue" in pattern or "held" in pattern else match.group(0)
                location = location.strip()
                # Avoid catching times and schedule items
                if not re.search(r"[0-9]{1,2}:[0-9]{2}\s*(?:AM|PM)", location) and location not in page_text_lower and len(location) > 3 and len(location) < 100:
                    return location[:100]

        return None

    def _extract_mode(self, soup: BeautifulSoup, page_text: str, location: str | None) -> str | None:
        """Extract event mode (online/offline/hybrid)."""
        page_text_lower = page_text.lower()

        if "hybrid" in page_text_lower:
            return "hybrid"
        if "virtual" in page_text_lower or "online" in page_text_lower or "remote" in page_text_lower:
            return "online"
        if location and location.lower() == "virtual":
            return "online"
        if "in-person" in page_text_lower or "offline" in page_text_lower:
            return "offline"

        # Default based on location
        if location and location.lower() != "virtual":
            return "offline"

        return "online"

    def _extract_dates(self, soup: BeautifulSoup, page_text: str) -> tuple[datetime | None, datetime | None]:
        """Extract start and end dates."""
        start_date = None
        end_date = None

        # Look for date patterns
        date_patterns = [
            r"(?:Start|Begin|From|Starts?|Date)[\s:]+([A-Za-z]+ \d{1,2},?\s*\d{4})",
            r"(?:End|Until|Through|Ends?)[\s:]+([A-Za-z]+ \d{1,2},?\s*\d{4})",
            r"(\w{3,}\s+\d{1,2},?\s+\d{4})",
        ]

        found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                parsed = parse_date(match)
                if parsed:
                    found_dates.append(parsed)

        # Sort and assign
        if found_dates:
            found_dates.sort()
            start_date = found_dates[0]
            if len(found_dates) > 1:
                end_date = found_dates[-1]

        return start_date, end_date

    def _extract_deadline(self, soup: BeautifulSoup, page_text: str) -> datetime | None:
        """Extract registration/submission deadline."""
        # Look for deadline patterns
        deadline_patterns = [
            r"(?:Deadline|Registration Closes?|Closes?).*?:\s*([A-Za-z]+ \d{1,2},? \d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
            r"by\s+([A-Za-z]+ \d{1,2},? \d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
        ]

        for pattern in deadline_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                deadline = parse_date(match.group(1))
                if deadline:
                    return deadline

        return None

    def _extract_prize_money(self, soup: BeautifulSoup, page_text: str) -> str | None:
        """Extract prize money information."""
        # Look for prize patterns in text
        prize_patterns = [
            r"(?:Prize|Reward|Prizes|Prize Pool)\s*(?:\(s\))?\s*:?\s*([^\n|]+(?:USD|\$|€|£|INR|₹)?[^\n|]*)",
            r"(\$[0-9,]+(?:\s*(?:to|-)\s*\$?[0-9,]+)?(?:\s*(?:USD|per person|total))?)",
            r"(₹[0-9,]+(?:\s*(?:to|-)\s*₹?[0-9,]+)?)",
            r"([0-9]{2,},?[0-9]{3,}(?:\s*(?:USD|INR|dollars|rupees))?)",
        ]

        for pattern in prize_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                prize = match.group(1) if "Prize" in pattern else match.group(0)
                prize = prize.strip()
                if prize and prize.lower() not in ["no", "none", "na", "n/a"]:
                    # Clean up the prize text
                    prize = re.sub(r"\s+", " ", prize)
                    return prize[:200]

        return None

    def _extract_team_size(self, soup: BeautifulSoup, page_text: str) -> str | None:
        """Extract team size constraints."""
        patterns = [
            r"(?:Max |Minimum )?Team Size\s*:?\s*([1-9]\s*(?:to|-)\s*[0-9]{1,2}|[1-9][0-9]?)\s*(?:members?|people|participants)?",
            r"Teams? (?:of up to|up to|of)\s*([0-9]{1,2})\s*(?:members?|people)",
            r"(?:Individual|Solo)\s+participation",
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                size = match.group(1) if "to" in pattern else match.group(0)
                if size:
                    return size.strip()[:100]

        return None

    def _extract_domains(self, soup: BeautifulSoup, page_text: str) -> list[str]:
        """Extract domain/track information."""
        domains = []

        # Look for track/category information
        for selector in ["[class*='track']", "[class*='category']", "[class*='tag']", "[class*='domain']"]:
            for elem in soup.select(selector):
                text = elem.get_text(strip=True)
                if text and 2 < len(text) < 50:
                    domains.append(text)

        # Look for domain keywords in text
        domain_keywords = [
            "machine learning",
            "nlp",
            "computer vision",
            "reinforcement learning",
            "generative models",
            "ai",
            "deep learning",
        ]

        for keyword in domain_keywords:
            if keyword.lower() in page_text.lower():
                domains.append(keyword.title())

        return list(set(domains))

    def _extract_registration_fee(self, soup: BeautifulSoup, page_text: str) -> str | None:
        """Extract registration fee information."""
        page_text_lower = page_text.lower()

        if "free" in page_text_lower:
            return "free"
        if "paid" in page_text_lower or "registration fee" in page_text_lower:
            return "paid"

        return None

    def _extract_status(self, soup: BeautifulSoup, page_text: str) -> str:
        """Extract event status."""
        page_text_lower = page_text.lower()

        if any(
            term in page_text_lower
            for term in ["closed", "ended", "finished", "completed", "archived"]
        ):
            return "closed"

        return "active"

    def _extract_eligibility(self, soup: BeautifulSoup, page_text: str) -> list[str]:
        """Extract eligibility criteria."""
        eligibility = []

        # Look for eligibility patterns
        eligibility_patterns = [
            r"Eligibility\s*:?\s*([^\n]+(?:students?|professionals?|everyone)[^\n]*)",
            r"(?:Open to|For|Restricted to)\s+([^\n.]+(?:students?|professionals?|everyone|anyone)[^\n.]*)",
            r"Who can apply\?[^\n]*\n?\s*([^\n]+)",
        ]

        for pattern in eligibility_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                criteria = match.group(1).strip()
                if criteria and len(criteria) > 10:
                    # Clean up the text
                    criteria = re.sub(r"\s+", " ", criteria)
                    eligibility.append(criteria[:200])
                    break  # Only take the first match

        return eligibility
