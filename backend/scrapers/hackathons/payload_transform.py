from dataclasses import asdict
from datetime import datetime

from backend.core.opportunity_enums import parse_opportunity_status, parse_opportunity_type
from backend.scrapers.base import ScrapedOpportunity
from backend.scrapers.hackathons.common import clean_description, dedupe_text_list, normalize_title, parse_date, sanitize_mode


_MAX_LEN = {
    "title": 500,
    "title_normalized": 500,
    "url": 1000,
    "source": 50,
    "mode": 20,
    "location": 300,
    "prize_money": 200,
    "registration_fee": 100,
    "team_size": 50,
}


def _nullable_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _truncate(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    limit = _MAX_LEN.get(field)
    if not limit:
        return value
    return value[:limit]


def _normalize_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        tokens = [token.strip() for token in value.split(";")]
        return dedupe_text_list([token for token in tokens if token])
    return dedupe_text_list(value)


def _normalize_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return parse_date(value.strip())
    return None


def _normalize_registration_fee(value: str | None) -> str | None:
    token = _nullable_str(value)
    if not token:
        return None
    token_l = token.lower()
    if "free" in token_l:
        return "free"
    if "paid" in token_l:
        return "paid"
    return _truncate(token_l, "registration_fee")


def _normalize_status(value: str | None) -> str:
    return parse_opportunity_status(value).value


def _normalize_opportunity_type(value: str | None) -> str:
    return parse_opportunity_type(value).value


def transform_hackathon_payload(item: ScrapedOpportunity, default_source: str) -> dict | None:
    payload = asdict(item)

    title = _truncate(_nullable_str(payload.get("title")), "title")
    url = _truncate(_nullable_str(payload.get("url")), "url")
    if not title or not url:
        return None

    payload["title"] = title
    payload["url"] = url
    payload["opportunity_type"] = _normalize_opportunity_type(payload.get("opportunity_type"))
    payload["source"] = _truncate((_nullable_str(payload.get("source")) or default_source).lower(), "source")
    payload["title_normalized"] = _truncate(normalize_title(title), "title_normalized")

    payload["description"] = clean_description(payload.get("description"))
    payload["mode"] = _truncate(sanitize_mode(_nullable_str(payload.get("mode"))), "mode")
    payload["location"] = _truncate(_nullable_str(payload.get("location")), "location")
    payload["prize_money"] = _truncate(_nullable_str(payload.get("prize_money")), "prize_money")
    payload["team_size"] = _truncate(_nullable_str(payload.get("team_size")), "team_size")

    payload["registration_fee"] = _normalize_registration_fee(payload.get("registration_fee"))
    payload["status"] = _normalize_status(payload.get("status"))

    payload["domains"] = _normalize_list(payload.get("domains"))
    payload["skills"] = _normalize_list(payload.get("skills"))
    payload["eligibility"] = _normalize_list(payload.get("eligibility"))

    payload["start_date"] = _normalize_datetime(payload.get("start_date"))
    payload["end_date"] = _normalize_datetime(payload.get("end_date"))
    payload["deadline"] = _normalize_datetime(payload.get("deadline"))
    return payload
