import logging
import re
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import ProfessorResearchCache, UserProfessorHistory
from backend.scrapers.coldemail.csrankings import ProfessorCandidate, ScrapeDiagnostics, scrape_professors_from_csrankings


logger = logging.getLogger(__name__)

_CATALOG_BACKFILL_LIMIT = 300


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()


def _normalize_display(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_profile_url(value: str | None) -> str | None:
    normalized = _normalize_display(value)
    return normalized or None


def _candidate_from_cache(row: ProfessorResearchCache, display_country: str) -> ProfessorCandidate:
    return ProfessorCandidate(
        country=display_country,
        name=row.professor_name,
        university=row.university_name or None,
        profile_url=row.profile_url,
    )


def _find_catalog_row(db: Session, candidate: ProfessorCandidate) -> ProfessorResearchCache | None:
    profile_url = _normalize_profile_url(candidate.profile_url)
    if profile_url:
        row = db.execute(
            select(ProfessorResearchCache).where(ProfessorResearchCache.profile_url == profile_url)
        ).scalar_one_or_none()
        if row is not None:
            return row

    professor_name = _normalize_display(candidate.name).casefold()
    university_name = _normalize_display(candidate.university).casefold()
    if professor_name:
        return db.execute(
            select(ProfessorResearchCache).where(
                func.lower(ProfessorResearchCache.professor_name) == professor_name,
                func.lower(ProfessorResearchCache.university_name) == university_name,
            )
        ).scalar_one_or_none()
    return None


def _upsert_catalog_rows(db: Session, candidates: list[ProfessorCandidate], source: str = "csrankings") -> None:
    if not candidates:
        return

    now = datetime.now(timezone.utc)
    for candidate in candidates:
        profile_url = _normalize_profile_url(candidate.profile_url)
        if not profile_url:
            continue

        country_key = _normalize_key(candidate.country)
        professor_name = _normalize_display(candidate.name)
        university_name = _normalize_display(candidate.university)

        row = _find_catalog_row(db, candidate)
        if row is None:
            row = ProfessorResearchCache(
                source=source,
                country=country_key or None,
                profile_url=profile_url,
                professor_name=professor_name,
                university_name=university_name,
                publications_json=[],
                publication_count=0,
                fetched_at=now,
            )
            db.add(row)
            continue

        if country_key and row.country != country_key:
            row.country = country_key
        if row.profile_url != profile_url:
            row.profile_url = profile_url
        if professor_name and row.professor_name != professor_name:
            row.professor_name = professor_name
        if university_name and row.university_name != university_name:
            row.university_name = university_name


def _select_catalog_rows_for_country(
    db: Session,
    user_id,
    country_key: str,
    limit: int,
) -> list[ProfessorResearchCache]:
    stmt = (
        select(ProfessorResearchCache)
        .outerjoin(
            UserProfessorHistory,
            and_(
                UserProfessorHistory.user_id == user_id,
                func.lower(UserProfessorHistory.country) == country_key,
                UserProfessorHistory.profile_url == ProfessorResearchCache.profile_url,
            ),
        )
        .where(
            func.lower(ProfessorResearchCache.country) == country_key,
            ProfessorResearchCache.profile_url.is_not(None),
        )
        .order_by(
            UserProfessorHistory.last_seen_at.asc().nullsfirst(),
            func.coalesce(UserProfessorHistory.seen_count, 0).asc(),
            ProfessorResearchCache.professor_name.asc(),
            ProfessorResearchCache.profile_url.asc(),
        )
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def _country_catalog_exists(db: Session, country_key: str) -> bool:
    return (
        db.execute(
            select(func.count())
            .select_from(ProfessorResearchCache)
            .where(func.lower(ProfessorResearchCache.country) == country_key)
        ).scalar_one()
        > 0
    )


def record_professor_seen(db: Session, user_id, candidate: ProfessorCandidate) -> None:
    profile_url = _normalize_profile_url(candidate.profile_url)
    if not profile_url:
        return

    country_key = _normalize_key(candidate.country)
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(UserProfessorHistory).where(
            UserProfessorHistory.user_id == user_id,
            func.lower(UserProfessorHistory.country) == country_key,
            UserProfessorHistory.profile_url == profile_url,
        )
    ).scalar_one_or_none()

    if row is None:
        row = UserProfessorHistory(
            user_id=user_id,
            country=country_key,
            profile_url=profile_url,
            seen_count=1,
            last_seen_at=now,
        )
        db.add(row)
        return

    row.country = country_key
    row.profile_url = profile_url
    row.seen_count = (row.seen_count or 0) + 1
    row.last_seen_at = now


async def resolve_professor_candidates_for_generation(
    db: Session,
    user_id,
    countries: list[str],
    website: str,
    max_professors_per_country: int,
) -> tuple[list[ProfessorCandidate], ScrapeDiagnostics]:
    selected: list[ProfessorCandidate] = []
    diagnostics = ScrapeDiagnostics(
        unsupported_countries=[],
        page_load_failures={},
        countries_with_no_candidates=[],
    )

    seen_country_keys: set[str] = set()
    display_country_by_key: dict[str, str] = {}
    ordered_country_keys: list[str] = []
    for country in countries:
        display_country = _normalize_display(country)
        country_key = _normalize_key(display_country)
        if not country_key or country_key in seen_country_keys:
            continue
        seen_country_keys.add(country_key)
        display_country_by_key[country_key] = display_country
        ordered_country_keys.append(country_key)

    for country_key in ordered_country_keys:
        country_display = display_country_by_key[country_key]
        rows = _select_catalog_rows_for_country(db, user_id, country_key, max_professors_per_country)
        country_has_catalog = _country_catalog_exists(db, country_key)

        if not rows and not country_has_catalog:
            logger.info("Professor catalog missing for %s; backfilling from CSRankings", country_display)
            scraped_rows, scrape_diagnostics = await scrape_professors_from_csrankings(
                website=website,
                countries=[country_display],
                max_professors_per_country=_CATALOG_BACKFILL_LIMIT,
            )
            diagnostics.unsupported_countries.extend(scrape_diagnostics.unsupported_countries)
            diagnostics.page_load_failures.update(scrape_diagnostics.page_load_failures)
            diagnostics.countries_with_no_candidates.extend(scrape_diagnostics.countries_with_no_candidates)

            if scraped_rows:
                _upsert_catalog_rows(db, scraped_rows)
                db.commit()
                rows = _select_catalog_rows_for_country(db, user_id, country_key, max_professors_per_country)

        if not rows:
            if country_display not in diagnostics.countries_with_no_candidates:
                diagnostics.countries_with_no_candidates.append(country_display)
            continue

        selected.extend(_candidate_from_cache(row, country_display) for row in rows)

    return selected, diagnostics
