import asyncio
import json
import logging
import re
from html import unescape

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.base import BaseScraper, ScrapedOpportunity
from backend.scrapers.hackathons.common import dedupe_text_list, parse_date, sanitize_mode

logger = logging.getLogger(__name__)


class UnstopScraper(BaseScraper):
    source = "unstop"
    _base_url = "https://unstop.com"
    _listing_url = "https://unstop.com/api/public/opportunity/search-result"
    _detail_url = "https://unstop.com/api/public/competition/{competition_id}?round_lang=1"
    _page_size = 18
    _max_items = None
    _listing_page_delay_seconds = 0.35
    _detail_delay_seconds = 0.3

    async def scrape(self) -> list[ScrapedOpportunity]:
        rows: list[ScrapedOpportunity] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://unstop.com/competitions?oppstatus=open",
        }

        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
            listing_items = await self._fetch_listing_items(client)
            for item in listing_items:
                row = await self._build_row(client, item)
                if row:
                    rows.append(row)
                await asyncio.sleep(self._detail_delay_seconds)

        return rows

    async def _fetch_listing_items(self, client: httpx.AsyncClient) -> list[dict]:
        items: list[dict] = []
        seen_ids: set[int] = set()
        page = 1

        while True:
            try:
                response = await client.get(
                    self._listing_url,
                    params={
                        "opportunity": "competitions",
                        "page": page,
                        "per_page": self._page_size,
                        "oppstatus": "open",
                        "sortBy": "",
                        "orderBy": "",
                        "filter_condition": "",
                        "undefined": "true",
                    },
                )
                response.raise_for_status()
                payload = response.json() or {}
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Unstop: failed to fetch listing page=%s (%s)", page, exc)
                break

            page_items = payload.get("data", {}).get("data", [])
            if not page_items:
                break

            for item in page_items:
                competition_id = item.get("id")
                if not competition_id or competition_id in seen_ids:
                    continue
                seen_ids.add(competition_id)
                items.append(item)

            next_page_url = payload.get("data", {}).get("next_page_url")
            current_page = payload.get("data", {}).get("current_page") or page
            last_page = payload.get("data", {}).get("last_page")
            if last_page is not None:
                try:
                    if int(current_page) >= int(last_page):
                        break
                except (TypeError, ValueError):
                    if not next_page_url:
                        break
            elif not next_page_url:
                break
            page += 1
            await asyncio.sleep(self._listing_page_delay_seconds)

        return items

    async def _build_row(self, client: httpx.AsyncClient, listing_item: dict) -> ScrapedOpportunity | None:
        competition_id = listing_item.get("id")
        if not competition_id:
            return None

        detail_item = await self._fetch_detail_item(client, competition_id)
        competition = detail_item or listing_item

        title = self._pick_first_text(competition.get("title"), listing_item.get("title"))
        url = self._build_opportunity_url(competition, listing_item)
        if not title or not url:
            return None

        regn_requirements = competition.get("regnRequirements") or listing_item.get("regnRequirements") or {}
        details_html = self._pick_first_text(competition.get("details"), listing_item.get("details"))
        details_text = self._to_text(details_html)

        filters = competition.get("filters") or listing_item.get("filters") or []
        domains = dedupe_text_list(
            self._extract_filter_names(filters)
            + self._extract_named_values(competition.get("workfunction") or listing_item.get("workfunction"))
            + self._extract_named_values(competition.get("assignedTag") or listing_item.get("assignedTag"))
            + self._extract_named_values(competition.get("tags") or listing_item.get("tags"))
        )

        skills = dedupe_text_list(
            self._extract_named_values(competition.get("skills"))
            + self._extract_named_values(competition.get("required_skills") or listing_item.get("required_skills"))
        )

        eligibility = dedupe_text_list(
            self._extract_eligibility_from_filters(filters)
            + self._extract_eligibility_from_regn(regn_requirements)
        )

        location = self._extract_location(
            competition.get("address_with_country_logo") or listing_item.get("address_with_country_logo"),
            competition.get("location") or listing_item.get("location"),
            competition.get("locations") or listing_item.get("locations"),
        )

        mode = sanitize_mode(
            self._derive_mode(
                regn_requirements=regn_requirements,
                location=location,
                text=details_text,
            )
        )

        start_date = parse_date(
            self._pick_first_text(
                regn_requirements.get("start_regn_dt"),
                competition.get("start_date"),
                listing_item.get("start_date"),
            )
        )
        end_date = parse_date(self._pick_first_text(competition.get("end_date"), listing_item.get("end_date")))
        deadline = parse_date(self._pick_first_text(regn_requirements.get("end_regn_dt")))

        return ScrapedOpportunity(
            opportunity_type="hackathon",
            title=title,
            url=url,
            source=self.source,
            description=details_text or None,
            domains=domains,
            skills=skills,
            mode=mode,
            location=location,
            start_date=start_date,
            end_date=end_date,
            deadline=deadline,
            prize_money=self._format_prize_money(competition.get("prizes") or listing_item.get("prizes")),
            registration_fee=self._derive_registration_fee(
                is_paid=competition.get("isPaid", listing_item.get("isPaid")),
                text=details_text,
            ),
            team_size=self._format_team_size(regn_requirements),
            eligibility=eligibility,
            status=self._map_status(competition.get("status") or listing_item.get("status")),
        )

    async def _fetch_detail_item(self, client: httpx.AsyncClient, competition_id: int) -> dict:
        try:
            response = await client.get(self._detail_url.format(competition_id=competition_id))
            response.raise_for_status()
            payload = response.json() or {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Unstop: detail fetch failed id=%s (%s)", competition_id, exc)
            return {}

        return payload.get("data", {}).get("competition") or {}

    def _build_opportunity_url(self, competition: dict, listing_item: dict) -> str | None:
        for candidate in (
            competition.get("seo_url"),
            listing_item.get("seo_url"),
            competition.get("public_url"),
            listing_item.get("public_url"),
        ):
            if not candidate or not isinstance(candidate, str):
                continue
            normalized = candidate.strip()
            if not normalized:
                continue
            if normalized.startswith("http"):
                return normalized.split("?", maxsplit=1)[0]
            if not normalized.startswith("/"):
                normalized = f"/{normalized}"
            return f"{self._base_url}{normalized}".split("?", maxsplit=1)[0]
        return None

    @staticmethod
    def _pick_first_text(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return None

    @staticmethod
    def _to_text(html_value: str | None) -> str:
        if not html_value:
            return ""
        text = BeautifulSoup(html_value, "html.parser").get_text(separator=" ", strip=True)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2500]

    def _extract_filter_names(self, filters: object) -> list[str]:
        if not isinstance(filters, list):
            return []
        values: list[str] = []
        for item in filters:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                values.append(name.strip())
        return values

    def _extract_eligibility_from_filters(self, filters: object) -> list[str]:
        if not isinstance(filters, list):
            return []
        values: list[str] = []
        for item in filters:
            if not isinstance(item, dict):
                continue
            if str(item.get("type", "")).lower() != "eligible":
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                values.append(name.strip())
        return values

    def _extract_named_values(self, value: object) -> list[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []

        if isinstance(value, dict):
            values: list[str] = []
            for key in ("name", "title", "tag", "label", "skill", "skill_name", "value"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    values.append(candidate.strip())
            return values

        if isinstance(value, list):
            values: list[str] = []
            for item in value:
                values.extend(self._extract_named_values(item))
            return values

        return []

    def _extract_eligibility_from_regn(self, regn_requirements: object) -> list[str]:
        if not isinstance(regn_requirements, dict):
            return []

        eligibility_raw = regn_requirements.get("eligibility")
        if not isinstance(eligibility_raw, str) or not eligibility_raw.strip():
            return []

        try:
            eligibility_obj = json.loads(eligibility_raw)
        except (TypeError, ValueError):
            return []

        if not isinstance(eligibility_obj, dict):
            return []

        results: list[str] = []

        sector = eligibility_obj.get("sector")
        if isinstance(sector, list):
            for item in sector:
                if isinstance(item, str) and item.strip() and item.strip().lower() != "all":
                    results.append(item.strip().replace("_", " ").title())

        track_labels = {
            "engineering": "Engineering",
            "bSchools": "Business",
            "arts": "Arts",
            "medicine": "Medicine",
            "law": "Law",
        }
        for key, label in track_labels.items():
            values = eligibility_obj.get(key)
            if isinstance(values, list) and values:
                has_specific = any(
                    isinstance(item, dict)
                    or (isinstance(item, str) and item.lower() not in {"all", "allcourses"})
                    for item in values
                )
                if has_specific:
                    results.append(label)

        return results

    def _extract_location(
        self,
        address_obj: object,
        fallback_location: object,
        locations: object,
    ) -> str | None:
        if isinstance(address_obj, dict):
            chunks: list[str] = []
            for key in ("address", "city", "state"):
                value = address_obj.get(key)
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
            country = address_obj.get("country")
            if isinstance(country, dict):
                country_name = country.get("name")
                if isinstance(country_name, str) and country_name.strip():
                    chunks.append(country_name.strip())
            if chunks:
                return ", ".join(dedupe_text_list(chunks))[:280]

        if isinstance(locations, list):
            location_tokens = self._extract_named_values(locations)
            if location_tokens:
                return ", ".join(dedupe_text_list(location_tokens))[:280]

        if isinstance(fallback_location, str) and fallback_location.strip():
            return fallback_location.strip()[:280]

        return None

    @staticmethod
    def _derive_mode(regn_requirements: object, location: str | None, text: str) -> str | None:
        token = ""
        if isinstance(regn_requirements, dict):
            raw = regn_requirements.get("work_location_type")
            if isinstance(raw, str):
                token = raw.strip().lower()

        haystack = f"{location or ''} {text}".lower()
        has_online_signal = "online" in haystack or "virtual" in haystack or "remote" in haystack
        has_offline_signal = (
            "offline" in haystack
            or "in-person" in haystack
            or "in person" in haystack
            or "onsite" in haystack
            or "on-site" in haystack
        )

        if token in {"online", "virtual", "remote"}:
            return "online"
        if token in {"hybrid"}:
            return "hybrid"
        if token in {"city", "offline", "onsite", "campus", "on-site"}:
            # Unstop can report `city` even for online rounds. Prefer page signals when present.
            if has_online_signal and not has_offline_signal:
                return "online"
            if has_online_signal and has_offline_signal:
                return "hybrid"
            return "offline"

        if "hybrid" in haystack:
            return "hybrid"
        if has_online_signal:
            return "online"
        if has_offline_signal:
            return "offline"
        return None

    @staticmethod
    def _format_team_size(regn_requirements: object) -> str | None:
        if not isinstance(regn_requirements, dict):
            return None

        min_size = regn_requirements.get("min_team_size")
        max_size = regn_requirements.get("max_team_size")

        try:
            min_value = int(min_size) if min_size is not None else None
            max_value = int(max_size) if max_size is not None else None
        except (TypeError, ValueError):
            return None

        if min_value is None and max_value is None:
            return None
        if min_value is not None and max_value is not None:
            if min_value == max_value:
                if min_value == 1:
                    return "individual"
                return f"{min_value} members"
            return f"{min_value}-{max_value} members"
        value = min_value if min_value is not None else max_value
        if value == 1:
            return "individual"
        return f"{value} members"

    @staticmethod
    def _format_prize_money(prizes: object) -> str | None:
        if not isinstance(prizes, list):
            return None

        entries: list[str] = []
        total_inr = 0
        has_total = False

        for prize in prizes:
            if not isinstance(prize, dict):
                continue

            rank = str(prize.get("rank") or "Prize").strip()
            cash = prize.get("cash")
            currency_code = prize.get("currencyCode") or "INR"

            amount: int | None = None
            if isinstance(cash, (int, float)):
                amount = int(cash)
            elif isinstance(cash, str):
                token = cash.strip().replace(",", "")
                if token.isdigit():
                    amount = int(token)

            if amount and amount > 0:
                if str(currency_code).upper() == "INR":
                    total_inr += amount
                    has_total = True
                entries.append(f"{rank}: {currency_code} {amount:,}")
                continue

            others = prize.get("others")
            if isinstance(others, str) and others.strip():
                entries.append(f"{rank}: {others.strip()}")

        if has_total and total_inr > 0:
            summary = f"INR {total_inr:,} total"
            if entries:
                return f"{summary} ({'; '.join(entries[:3])})"[:200]
            return summary[:200]

        if entries:
            return "; ".join(entries[:3])[:200]
        return None

    @staticmethod
    def _derive_registration_fee(is_paid: object, text: str) -> str | None:
        if isinstance(is_paid, bool):
            return "paid" if is_paid else "free"

        token = text.lower()
        if re.search(r"\b(no fee|no cost|free)\b", token):
            return "free"
        if re.search(r"\b(paid|registration fee|entry fee)\b", token):
            return "paid"
        return None

    @staticmethod
    def _map_status(status: object) -> str:
        token = str(status or "").strip().lower()
        if token in {"upcoming", "scheduled"}:
            return "upcoming"
        return "active"