import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert

from backend.core.opportunity_enums import parse_opportunity_status, parse_opportunity_type
from backend.infra.postgres.session import SessionLocal
from backend.infra.postgres.tables import Opportunity
from backend.scrapers.base import ScrapedOpportunity
from backend.scrapers.hackathons import (
    DevfolioScraper,
    Hack2skillScraper,
    HackerearthScraper,
    KaggleScraper,
    NeurIPSScraper,
    UnstopScraper,
)
from backend.scrapers.hackathons.common import clean_description, dedupe_text_list, normalize_title
from backend.scrapers.hackathons.payload_transform import transform_hackathon_payload
from backend.services.admin.app_config import record_admin_log


logger = logging.getLogger(__name__)

PLAYWRIGHT_SOURCES = {"unstop", "hack2skill", "hackerearth"}

SCRAPER_REGISTRY = {
    "devfolio": DevfolioScraper,
    "unstop": UnstopScraper,
    "hackerearth": HackerearthScraper,
    "hack2skill": Hack2skillScraper,
    "kaggle": KaggleScraper,
    "neurips": NeurIPSScraper,
}

SOURCE_DEFAULTS = {
    "devfolio": "devfolio",
    "unstop": "unstop",
    "hackerearth": "hackerearth",
    "hack2skill": "hack2skill",
    "kaggle": "kaggle",
    "neurips": "neurips",
}


def _normalize_payload(item: ScrapedOpportunity) -> dict:
    payload = asdict(item)
    payload["title"] = payload["title"].strip()
    payload["title_normalized"] = normalize_title(payload["title"])
    payload["opportunity_type"] = parse_opportunity_type(payload.get("opportunity_type")).value
    payload["status"] = parse_opportunity_status(payload.get("status")).value
    payload["description"] = clean_description(payload.get("description"))
    payload["domains"] = dedupe_text_list(payload.get("domains"))
    payload["skills"] = dedupe_text_list(payload.get("skills"))
    payload["eligibility"] = dedupe_text_list(payload.get("eligibility"))
    return payload


def _sanitize_for_storage(payload: dict) -> dict:
    payload["opportunity_type"] = parse_opportunity_type(payload.get("opportunity_type")).value
    payload["status"] = parse_opportunity_status(payload.get("status")).value
    payload["description"] = clean_description(payload.get("description"))
    return payload


async def _run_scraper_with_windows_playwright_support(
    source_name: str,
    scraper: object,
) -> list[ScrapedOpportunity]:
    if os.name != "nt" or source_name not in PLAYWRIGHT_SOURCES:
        return await scraper.scrape()

    def _run_in_thread() -> list[ScrapedOpportunity]:
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(scraper.scrape())
        finally:
            loop.close()

    return await asyncio.to_thread(_run_in_thread)


async def run_selected_scrapers(
    selected_sources: list[str] | None = None,
    emit_log: Callable[[str], None] | None = None,
) -> dict:
    source_names = selected_sources or list(SCRAPER_REGISTRY.keys())
    by_source: dict[str, int] = {}
    scraped_total = 0
    saved_total = 0
    logs: list[str] = []

    def log(message: str) -> None:
        record_admin_log(logs, message, emit_log)

    log(f"Starting hackathon scraper run for {', '.join(source_names)}")

    with SessionLocal() as session:
        for source_name in source_names:
            scraper_cls = SCRAPER_REGISTRY.get(source_name)
            if scraper_cls is None:
                by_source[source_name] = 0
                log(f"{source_name}: no scraper registered, skipping")
                continue

            try:
                scraper = scraper_cls()
                log(f"{source_name}: starting scrape")
                rows = await _run_scraper_with_windows_playwright_support(source_name, scraper)
                scraped_total += len(rows)
                by_source[source_name] = len(rows)

                saved_for_source = 0
                for item in rows:
                    default_source = SOURCE_DEFAULTS.get(source_name)
                    normalized = (
                        transform_hackathon_payload(item, default_source=default_source)
                        if default_source
                        else _normalize_payload(item)
                    )
                    if not normalized:
                        continue
                    normalized = _sanitize_for_storage(normalized)
                    if not normalized["title"] or not normalized["url"]:
                        continue

                    statement = insert(Opportunity).values(**normalized)
                    statement = statement.on_conflict_do_update(
                        constraint="uq_opportunity_title_source",
                        set_={
                            "url": statement.excluded.url,
                            "description": statement.excluded.description,
                            "domains": statement.excluded.domains,
                            "skills": statement.excluded.skills,
                            "mode": statement.excluded.mode,
                            "location": statement.excluded.location,
                            "start_date": statement.excluded.start_date,
                            "end_date": statement.excluded.end_date,
                            "deadline": statement.excluded.deadline,
                            "prize_money": statement.excluded.prize_money,
                            "registration_fee": statement.excluded.registration_fee,
                            "team_size": statement.excluded.team_size,
                            "eligibility": statement.excluded.eligibility,
                            "status": statement.excluded.status,
                        },
                    )
                    session.execute(statement)
                    saved_total += 1
                    saved_for_source += 1

                log(f"{source_name}: scraped {len(rows)} item(s), saved {saved_for_source} item(s)")
            except Exception as exc:
                logger.exception("Hackathon scraper failed for source=%s", source_name)
                by_source[source_name] = 0
                log(f"{source_name}: failed with {type(exc).__name__}: {exc}")
                continue

        session.commit()

    log(f"Hackathon scraper run complete: scraped {scraped_total} item(s), saved {saved_total} item(s)")

    return {
        "total_scraped": scraped_total,
        "total_saved": saved_total,
        "by_source": by_source,
        "logs": logs,
    }
