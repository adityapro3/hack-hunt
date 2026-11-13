import re
from datetime import datetime

from dateutil import parser as date_parser


_MARKDOWN_SYMBOL_RE = re.compile(r"[#*_`]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(value)
    except (ValueError, TypeError, OverflowError):
        return None


def sanitize_mode(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip().lower()
    if "online" in token:
        return "online"
    if "offline" in token or "onsite" in token:
        return "offline"
    if "hybrid" in token:
        return "hybrid"
    return token


def dedupe_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        if not raw:
            continue
        item = raw.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def clean_description(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    text = _MARKDOWN_SYMBOL_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None
