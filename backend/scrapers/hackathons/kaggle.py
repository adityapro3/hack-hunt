import asyncio
import ast
import logging
import re
import time

import requests

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date

logger = logging.getLogger(__name__)


class KaggleScraper(BaseScraper):
    source = "kaggle"

    _base_url = "https://www.kaggle.com"
    _list_api_url = "https://www.kaggle.com/api/i/competitions.CompetitionService/ListCompetitions"
    _competition_api_url = "https://www.kaggle.com/api/i/competitions.CompetitionService/GetCompetition"
    _pages_api_url = "https://www.kaggle.com/api/i/competitions.PageService/ListPages"

    _page_size = 20
    _max_pages = 3
    _parallelism = 3
    _timeout_seconds = 45
    _detail_request_delay_seconds = 0.25
    _listing_page_delay_seconds = 0.35

    _api_request_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.kaggle.com/competitions?hostSegmentIdFilter=1&page=1",
    }

    async def scrape(self) -> list[ScrapedOpportunity]:
        listing_items = await self._extract_listing_via_api()
        if not listing_items:
            logger.warning("Kaggle: no listing items found from API")
            return []

        semaphore = asyncio.Semaphore(self._parallelism)

        async def _enrich(item: dict) -> ScrapedOpportunity | None:
            async with semaphore:
                await asyncio.sleep(self._detail_request_delay_seconds)
                detail = await self._extract_detail_via_api(
                    competition_name=item.get("competition_name") or "",
                    competition_id=item.get("competition_id"),
                )
                merged = self._merge_listing_and_detail(item, detail)
                return self._to_scraped_opportunity(merged)

        tasks = [_enrich(item) for item in listing_items]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        rows: list[ScrapedOpportunity] = []
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.warning("Kaggle: detail enrichment failed (%s)", outcome)
                continue
            if outcome:
                rows.append(outcome)

        return rows

    async def _extract_listing_via_api(self) -> list[dict]:
        results: list[dict] = []
        seen_urls: set[str] = set()

        next_page_token: str | None = None
        seen_page_tokens: set[str] = set()

        for page_number in range(1, self._max_pages + 1):
            params: dict[str, int | str] = {
                "hostSegmentIdFilter": 1,
                "pageSize": self._page_size,
            }
            if next_page_token is not None:
                params["pageToken"] = next_page_token

            try:
                payload = await asyncio.to_thread(
                    self._get_json_with_requests,
                    self._list_api_url,
                    params,
                )
            except Exception as exc:
                logger.warning("Kaggle: list API call failed on page %s (%s)", page_number, exc)
                break

            competitions = payload.get("competitions") or []
            if not competitions:
                break

            for entry in competitions:
                competition_name = (entry.get("competitionName") or "").strip()
                if not competition_name:
                    continue

                url = f"{self._base_url}/competitions/{competition_name}"
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                categories = entry.get("categories") or []
                domains = []
                for category in categories:
                    if not isinstance(category, dict):
                        continue
                    label = (category.get("displayName") or category.get("name") or "").strip()
                    if label:
                        domains.append(label)

                team_size = entry.get("maxTeamSize")
                results.append(
                    {
                        "url": url,
                        "competition_name": competition_name,
                        "competition_id": entry.get("id"),
                        "title": (entry.get("title") or competition_name.replace("-", " ")).strip(),
                        "listing_text": (entry.get("briefDescription") or "").strip(),
                        "domains": dedupe_text_list(domains),
                        "meta_line": (entry.get("hostName") or "").strip(),
                        "deadline_text": entry.get("deadline"),
                        "start_text": entry.get("dateEnabled") or entry.get("dateCreated"),
                        "end_text": None,
                        "prize_money": self._normalize_prize_reward(entry.get("reward")),
                        "team_size": str(team_size).strip() if team_size is not None else None,
                        "status": "active" if entry.get("launched", True) else "upcoming",
                        "mode": None,
                        "location": None,
                        "registration_fee": None,
                    }
                )

            raw_next_token = payload.get("nextPageToken")
            next_token = str(raw_next_token).strip() if raw_next_token is not None else ""
            if not next_token:
                break

            if next_token in seen_page_tokens:
                break
            seen_page_tokens.add(next_token)

            next_page_token = next_token
            await asyncio.sleep(self._listing_page_delay_seconds)

        return results

    async def _extract_detail_via_api(
        self,
        competition_name: str,
        competition_id: int | None,
    ) -> dict:
        if not competition_name and not competition_id:
            return {}

        competition_payload: dict = {}
        if competition_name:
            try:
                competition_payload = await asyncio.to_thread(
                    self._get_json_with_requests,
                    self._competition_api_url,
                    {"competitionName": competition_name},
                )
            except Exception as exc:
                logger.warning("Kaggle: competition API failed for %s (%s)", competition_name, exc)

        resolved_competition_id = competition_payload.get("id") or competition_id

        pages_payload: list[dict] = []
        if resolved_competition_id:
            try:
                pages_obj = await asyncio.to_thread(
                    self._get_json_with_requests,
                    self._pages_api_url,
                    {"competitionId": resolved_competition_id},
                )
                pages_payload = (pages_obj or {}).get("pages") or []
            except Exception as exc:
                logger.warning("Kaggle: pages API failed for competition id %s (%s)", resolved_competition_id, exc)

        page_texts: list[str] = []
        page_description = ""
        for page_item in pages_payload:
            if not isinstance(page_item, dict):
                continue

            content = (page_item.get("content") or "").strip()
            if not content:
                continue

            page_name = (page_item.get("name") or "").strip().lower()
            if page_name in {"rules", "citation"}:
                continue

            page_texts.append(content)
            if not page_description and page_name in {
                "description",
                "overview",
                "abstract",
                "data-description",
                "topics of interest",
            }:
                page_description = content

        categories = competition_payload.get("categories") or []
        domains = []
        for category in categories:
            if not isinstance(category, dict):
                continue
            label = (category.get("displayName") or category.get("name") or "").strip()
            if label:
                domains.append(label)

        organization = competition_payload.get("organization") or {}
        organization_name = ""
        if isinstance(organization, dict):
            organization_name = (organization.get("name") or "").strip()

        description = (
            (competition_payload.get("briefDescription") or "").strip()
            or page_description.strip()
            or (page_texts[0].strip() if page_texts else "")
        )

        all_text_parts = [description, organization_name, *page_texts]
        page_text = "\n\n".join([part for part in all_text_parts if part])

        reward = competition_payload.get("reward")
        prize_money = self._normalize_prize_reward(reward) or self._extract_first_match(
            [
                r"(?:prize(?:\s*pool)?|rewards?)\s*[:\-]?\s*([^|\n]{3,120})",
                r"(\$\s*[\d,]+(?:\.\d+)?|₹\s*[\d,]+(?:\.\d+)?)",
            ],
            page_text,
        )

        team_size = competition_payload.get("maxTeamSize")
        team_size_text = (str(team_size).strip() if team_size is not None else None) or self._extract_first_match(
            [
                r"team\s*size\s*[:\-]?\s*([^|\n]{1,50})",
                r"(solo|individual|\d+\s*(?:to|-)\s*\d+\s*(?:members?)?)",
            ],
            page_text,
        )

        return {
            "title": (competition_payload.get("title") or "").strip() or None,
            "description": description or None,
            "domains": dedupe_text_list(domains),
            "meta_line": organization_name,
            "page_text": page_text,
            "deadline_text": competition_payload.get("deadline"),
            "start_text": competition_payload.get("dateEnabled") or competition_payload.get("dateCreated"),
            "end_text": None,
            "prize_money": prize_money,
            "registration_fee": self._infer_registration_fee(page_text),
            "team_size": team_size_text,
            "status": "active" if competition_payload.get("launched", True) else "upcoming",
            "location": None,
            "mode": self._infer_mode(page_text),
        }

    def _merge_listing_and_detail(self, listing_item: dict, detail: dict) -> dict:
        merged = {
            "title": listing_item.get("title"),
            "url": listing_item.get("url"),
            "description": listing_item.get("listing_text") or None,
            "domains": listing_item.get("domains") or [],
            "meta_line": listing_item.get("meta_line") or "",
            "page_text": listing_item.get("listing_text") or "",
            "deadline_text": listing_item.get("deadline_text"),
            "start_text": listing_item.get("start_text"),
            "end_text": listing_item.get("end_text"),
            "prize_money": listing_item.get("prize_money"),
            "registration_fee": listing_item.get("registration_fee"),
            "team_size": listing_item.get("team_size"),
            "status": listing_item.get("status") or "active",
            "location": listing_item.get("location"),
            "mode": listing_item.get("mode"),
        }

        for key, value in (detail or {}).items():
            if value in (None, "", []):
                continue
            merged[key] = value

        merged["domains"] = dedupe_text_list(
            [
                *(listing_item.get("domains") or []),
                *(detail.get("domains") or [] if detail else []),
            ]
        )
        return merged

    def _to_scraped_opportunity(self, payload: dict) -> ScrapedOpportunity | None:
        title = (payload.get("title") or "").strip()
        url = (payload.get("url") or "").strip()
        if not title or not url:
            return None

        all_text = payload.get("page_text") or ""
        deadline_text = payload.get("deadline_text") or self._extract_first_match(
            [
                r"(?:registration|submission)\s*(?:closes?|ends?|deadline)\s*[:\-]?\s*([^|\n]{4,80})",
                r"deadline\s*[:\-]?\s*([^|\n]{4,80})",
            ],
            all_text,
        )

        return ScrapedOpportunity(
            opportunity_type="Hackathon",
            title=title,
            url=url,
            source=self.source,
            description=payload.get("description") or None,
            domains=dedupe_text_list(payload.get("domains") or []),
            skills=[],
            mode="online",
            location=None,
            start_date=parse_date(payload.get("start_text")),
            end_date=parse_date(payload.get("end_text")),
            deadline=parse_date(deadline_text),
            prize_money=self._nullable_text(payload.get("prize_money")),
            registration_fee=payload.get("registration_fee") or self._infer_registration_fee(all_text),
            team_size=self._nullable_text(payload.get("team_size")),
            eligibility=[],
            status=payload.get("status") or self._infer_status(payload.get("meta_line") or all_text),
        )

    def _get_json_with_requests(self, url: str, params: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._api_request_headers,
                    timeout=self._timeout_seconds,
                    allow_redirects=True,
                )
                response.raise_for_status()

                content_type = (response.headers.get("content-type") or "").lower()
                if "application/json" not in content_type:
                    head = response.text[:220].lower()
                    if "recaptcha" in head or "checking your browser" in head or "challenge" in head:
                        raise ValueError("Kaggle API returned challenge HTML")

                payload = response.json()
                if isinstance(payload, dict):
                    return payload
                raise ValueError("Kaggle API returned non-object JSON payload")
            except Exception as exc:
                last_error = exc
                time.sleep(0.8 * (attempt + 1))

        if last_error:
            raise last_error
        raise RuntimeError("Kaggle API request failed with unknown error")

    def _normalize_prize_reward(self, reward: object) -> str | None:
        if reward is None:
            return None

        if isinstance(reward, dict):
            currency = str(reward.get("id") or "").strip().upper()
            quantity = reward.get("quantity")
            clarification = self._nullable_text(reward.get("clarification"))

            total = None
            if isinstance(quantity, (int, float)):
                total = self._format_currency_amount(quantity, currency)

            clarification_text = self._summarize_clarification(clarification) if clarification else None

            if clarification_text and total:
                if total in clarification_text:
                    return clarification_text
                return f"{clarification_text}; total: {total}"

            if clarification_text:
                return clarification_text

            return total

        if isinstance(reward, str):
            token = reward.strip()
            if not token:
                return None

            if token.startswith("{") and token.endswith("}"):
                try:
                    parsed = ast.literal_eval(token)
                    if isinstance(parsed, dict):
                        return self._normalize_prize_reward(parsed)
                except Exception:
                    pass

            return self._summarize_clarification(token)

        return self._nullable_text(reward)

    @staticmethod
    def _format_currency_amount(quantity: int | float, currency: str) -> str:
        amount = f"{int(quantity):,}"
        if currency == "USD":
            return f"${amount}"
        if currency == "INR":
            return f"₹{amount}"
        if currency:
            return f"{currency} {amount}"
        return amount

    @staticmethod
    def _summarize_clarification(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        compact = compact.rstrip(";.,")

        first_prize_match = re.search(r"consisting of\s*(.+?)(?:;|$)", compact, re.IGNORECASE)
        additional_match = re.search(r"additional\s*([^;]+)", compact, re.IGNORECASE)

        first_prize = first_prize_match.group(1).strip() if first_prize_match else ""
        additional = additional_match.group(1).strip() if additional_match else ""

        if first_prize and additional:
            return f"1st prize: {first_prize}; additional: {additional}"
        if first_prize:
            return f"1st prize: {first_prize}"
        if additional:
            return f"additional: {additional}"

        return compact

    @staticmethod
    def _nullable_text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _extract_first_match(patterns: list[str], text: str) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1) if match.lastindex else match.group(0)
            cleaned = value.strip(" .,:;\t")
            if cleaned:
                return cleaned
        return None

    @staticmethod
    def _infer_mode(page_text: str) -> str | None:
        token = page_text.lower()
        if "hybrid" in token:
            return "hybrid"
        if "online" in token or "virtual" in token:
            return "online"
        if "offline" in token or "in-person" in token or "onsite" in token:
            return "offline"
        return None

    @staticmethod
    def _infer_registration_fee(page_text: str) -> str | None:
        token = page_text.lower()
        if re.search(r"\b(free|no fee|no cost)\b", token):
            return "free"
        if re.search(r"\b(paid|registration fee)\b", token):
            return "paid"
        return None

    @staticmethod
    def _infer_status(meta_text: str) -> str:
        token = meta_text.lower()
        if "coming soon" in token:
            return "upcoming"
        return "active"
