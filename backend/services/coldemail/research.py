import logging
import math
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import ProfessorResearchCache
from backend.scrapers.coldemail.arxiv import ResearchPublication, fetch_arxiv_publications_playwright
from backend.services.common.embeddings_generate import generate_embedding, generate_embeddings

from backend.services.coldemail.models import MatchedPublication


logger = logging.getLogger(__name__)

_MAX_PUBLICATIONS_TO_SCAN = 120
_LEXICAL_PREFILTER_CANDIDATES = 20
_RECENT_PUBLICATIONS_WINDOW = 40
_SEMANTIC_TOP_MATCHES = 3


def build_user_research_query(student_profile: dict, resume_text: str) -> str | None:
    blocks: list[str] = []
    interests = [str(item).strip() for item in student_profile.get("research_interests", []) if str(item).strip()]
    skills = [str(item).strip() for item in student_profile.get("technical_skills", []) if str(item).strip()]
    goal = str(student_profile.get("goal") or "").strip()

    if interests:
        blocks.append("Research interests: " + ", ".join(interests[:12]))
    if skills:
        blocks.append("Technical skills: " + ", ".join(skills[:20]))
    if goal:
        blocks.append(f"Academic goal: {goal[:220]}")

    cleaned_resume = (resume_text or "").strip()
    if cleaned_resume:
        blocks.append(f"Resume summary: {cleaned_resume[:2500]}")

    if not blocks:
        return None
    return "\n".join(blocks)


def _clean_cache_token(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _clean_profile_url(value: str | None) -> str:
    return _clean_cache_token(value)


def _clean_country(value: str | None) -> str:
    return _clean_cache_token(value).casefold()


def _serialize_publication(publication: ResearchPublication) -> dict:
    detail_url = getattr(publication, "detail_url", None) or getattr(publication, "url", None)
    payload = {
        "title": publication.title,
        "year": publication.year,
        "abstract": publication.abstract,
    }
    if isinstance(detail_url, str) and detail_url.strip():
        payload["detail_url"] = detail_url.strip()
    return payload


def _deserialize_publication(payload: dict) -> ResearchPublication | None:
    title = str(payload.get("title") or "").strip()
    if not title:
        return None
    year_value = payload.get("year")
    parsed_year = year_value if isinstance(year_value, int) else None
    abstract = str(payload.get("abstract") or "").strip() or None
    detail_url = str(payload.get("detail_url") or payload.get("url") or "").strip() or None
    return ResearchPublication(
        title=title,
        year=parsed_year,
        detail_url=detail_url,
        abstract=abstract,
    )


def _filter_publications_with_abstract(publications: list[ResearchPublication]) -> list[ResearchPublication]:
    return [
        publication
        for publication in publications
        if isinstance(publication.abstract, str) and publication.abstract.strip()
    ]


def _get_cached_row(
    db: Session,
    profile_url: str | None,
    professor_name: str | None,
    university_name: str | None,
) -> ProfessorResearchCache | None:
    clean_profile_url = _clean_profile_url(profile_url)
    if clean_profile_url:
        row = db.execute(
            select(ProfessorResearchCache).where(ProfessorResearchCache.profile_url == clean_profile_url)
        ).scalar_one_or_none()
        if row is not None:
            return row

    clean_professor_name = _clean_cache_token(professor_name)
    if clean_professor_name:
        clean_university_name = _clean_cache_token(university_name)
        return db.execute(
            select(ProfessorResearchCache).where(
                func.lower(ProfessorResearchCache.professor_name) == clean_professor_name.casefold(),
                func.lower(ProfessorResearchCache.university_name) == clean_university_name.casefold(),
            )
        ).scalar_one_or_none()

    return None


def _deserialize_cached_publications(row: ProfessorResearchCache | None) -> list[ResearchPublication]:
    if row is None:
        return []

    publications: list[ResearchPublication] = []
    for payload in row.publications_json or []:
        if not isinstance(payload, dict):
            continue
        parsed = _deserialize_publication(payload)
        if parsed is not None:
            publications.append(parsed)
    return publications


def _touch_cached_row_metadata(
    row: ProfessorResearchCache,
    profile_url: str | None,
    country: str | None,
    professor_name: str | None,
    university_name: str | None,
) -> bool:
    changed = False

    clean_profile_url = _clean_profile_url(profile_url)
    if clean_profile_url and row.profile_url != clean_profile_url:
        row.profile_url = clean_profile_url
        changed = True

    clean_country = _clean_country(country)
    if clean_country and row.country != clean_country:
        row.country = clean_country
        changed = True

    clean_professor_name = _clean_cache_token(professor_name)
    if clean_professor_name and row.professor_name != clean_professor_name:
        row.professor_name = clean_professor_name
        changed = True

    clean_university_name = _clean_cache_token(university_name)
    if clean_university_name and row.university_name != clean_university_name:
        row.university_name = clean_university_name
        changed = True

    return changed


def _upsert_cached_publications(
    db: Session,
    profile_url: str | None,
    country: str | None,
    professor_name: str,
    university_name: str | None,
    publications: list[ResearchPublication],
) -> None:
    if not publications:
        logger.info(
            "Skipping ArXiv cache upsert for (%s, %s): no publications returned",
            professor_name,
            university_name or "",
        )
        return

    row = _get_cached_row(db, profile_url, professor_name, university_name)
    clean_profile_url = _clean_profile_url(profile_url)
    clean_country = _clean_country(country)
    clean_professor_name = _clean_cache_token(professor_name)
    clean_university_name = _clean_cache_token(university_name)

    serialized = [_serialize_publication(publication) for publication in publications]
    if row is None:
        row = ProfessorResearchCache(
            source="arxiv",
            country=clean_country or None,
            profile_url=clean_profile_url or None,
            professor_name=clean_professor_name,
            university_name=clean_university_name,
            publications_json=serialized,
            publication_count=len(serialized),
            fetched_at=datetime.now(timezone.utc),
        )
        db.add(row)
    else:
        _touch_cached_row_metadata(
            row=row,
            profile_url=profile_url,
            country=country,
            professor_name=professor_name,
            university_name=university_name,
        )
        row.publications_json = serialized
        row.publication_count = len(serialized)
        row.fetched_at = datetime.now(timezone.utc)

    db.commit()


def _tokenize_for_matching(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= 3
    }


def _lexical_overlap_score(query_tokens: set[str], publication_tokens: set[str]) -> float:
    if not query_tokens or not publication_tokens:
        return 0.0

    overlap = len(query_tokens.intersection(publication_tokens))
    if overlap == 0:
        return 0.0

    return overlap / math.sqrt(len(query_tokens) * len(publication_tokens))


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for left, right in zip(vec_a, vec_b):
        dot += left * right
        norm_a += left * left
        norm_b += right * right

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _semantic_match_publications(
    publications: list[ResearchPublication],
    user_query: str | None,
    top_k: int = _SEMANTIC_TOP_MATCHES,
) -> list[MatchedPublication]:
    if not publications:
        return []

    if not user_query:
        return [
            MatchedPublication(
                title=publication.title,
                score=0.0,
                year=publication.year,
                detail_url=publication.detail_url,
                abstract=publication.abstract,
            )
            for publication in publications[:top_k]
        ]

    query_tokens = _tokenize_for_matching(user_query)

    recent_first = sorted(
        publications,
        key=lambda publication: (publication.year is not None, publication.year or 0),
        reverse=True,
    )
    recent_window = recent_first[:_RECENT_PUBLICATIONS_WINDOW]

    def publication_text(publication: ResearchPublication) -> str:
        if publication.abstract:
            return f"{publication.title}. {publication.abstract}"
        return publication.title

    lexical_ranked = sorted(
        recent_window,
        key=lambda publication: _lexical_overlap_score(
            query_tokens,
            _tokenize_for_matching(publication_text(publication)),
        ),
        reverse=True,
    )
    candidates = lexical_ranked[:_LEXICAL_PREFILTER_CANDIDATES]
    logger.info(
        "Semantic search started for professor publications: candidates=%s top_k=%s",
        len(candidates),
        top_k,
    )

    publication_texts = [publication_text(publication) for publication in candidates]

    try:
        embeddings = generate_embeddings([user_query, *publication_texts])
        if len(embeddings) != len(candidates) + 1:
            raise RuntimeError(
                f"Expected {len(candidates) + 1} embeddings but got {len(embeddings)}"
            )

        query_embedding = embeddings[0]
        publication_embeddings: list[list[float] | None] = embeddings[1:]
        logger.info(
            "Semantic search embeddings generated in batch for professor publications: candidates=%s",
            len(candidates),
        )
    except Exception as exc:
        logger.warning(
            "Batch embedding generation failed for professor publications; falling back to per-item generation: %s",
            exc,
        )

        try:
            query_embedding = generate_embedding(user_query)
            logger.info("Semantic search query embedding generated")
        except Exception as exc:
            logger.warning("Embedding generation failed for user query; falling back to lexical ranking: %s", exc)
            return [
                MatchedPublication(
                    title=publication.title,
                    score=0.0,
                    year=publication.year,
                    detail_url=publication.detail_url,
                    abstract=publication.abstract,
                )
                for publication in candidates[:top_k]
            ]

        publication_embeddings = []
        for publication_text_value in publication_texts:
            try:
                publication_embeddings.append(generate_embedding(publication_text_value))
            except Exception as exc:
                logger.warning("Failed embedding publication title for semantic ranking: %s", exc)
                publication_embeddings.append(None)

    scored: list[MatchedPublication] = []
    current_year = datetime.now(timezone.utc).year
    for publication, publication_embedding in zip(candidates, publication_embeddings):
        if publication_embedding is None:
            continue

        semantic_score = _cosine_similarity(query_embedding, publication_embedding)

        recency_boost = 0.0
        if publication.year:
            age_years = max(0, current_year - publication.year)
            recency_boost = max(0.0, 1.0 - (min(age_years, 15) / 15.0))

        final_score = (semantic_score * 0.9) + (recency_boost * 0.1)
        scored.append(
            MatchedPublication(
                title=publication.title,
                score=final_score,
                year=publication.year,
                detail_url=publication.detail_url,
                abstract=publication.abstract,
            )
        )

    if not scored:
        return [
            MatchedPublication(
                title=publication.title,
                score=0.0,
                year=publication.year,
                detail_url=publication.detail_url,
                abstract=publication.abstract,
            )
            for publication in candidates[:top_k]
        ]

    scored.sort(
        key=lambda item: (item.score, item.year is not None, item.year or 0),
        reverse=True,
    )
    top_results = scored[:top_k]
    logger.info(
        "Semantic search completed: scored=%s returned=%s",
        len(scored),
        len(top_results),
    )
    return top_results


def _format_research_context(matched: list[MatchedPublication], user_query: str | None) -> str:
    if not matched:
        return "Research profile was available, but publications could not be extracted."

    if not user_query:
        rendered = [f"{item.title} ({item.year})" if item.year else item.title for item in matched]
        return "Recent research: " + "; ".join(rendered)

    formatted: list[str] = []
    for index, item in enumerate(matched):
        line = (
            f"{index + 1}. {item.title}"
            + (f" ({item.year})" if item.year else "")
            + f" (semantic similarity: {item.score:.3f})"
        )
        if item.detail_url:
            line += f"\n   URL: {item.detail_url}"
        if item.abstract:
            line += f"\n   Abstract: {item.abstract[:700]}"
        formatted.append(line)

    return "Top semantically matched research to candidate profile:\n" + "\n".join(formatted)


async def fetch_research_summary(
    db: Session,
    profile_url: str | None,
    user_query: str | None = None,
    professor_name: str | None = None,
    university_name: str | None = None,
    country: str | None = None,
) -> str:
    cached_row = _get_cached_row(db, profile_url, professor_name, university_name)
    if cached_row is not None and _touch_cached_row_metadata(
        cached_row,
        profile_url=profile_url,
        country=country,
        professor_name=professor_name,
        university_name=university_name,
    ):
        db.commit()

    cached_publications = _deserialize_cached_publications(cached_row)
    cache_hit = bool(cached_publications)
    arxiv_publications = cached_publications
    should_refresh_cache = bool(professor_name) and not cache_hit

    if cache_hit and professor_name:
        logger.info(
            "Using cached ArXiv data for (%s, %s) pair (publications=%s)",
            professor_name,
            university_name or "",
            len(cached_publications),
        )

    if should_refresh_cache and professor_name:
        try:
            refreshed_publications = await fetch_arxiv_publications_playwright(
                professor_name,
                max_publications=_MAX_PUBLICATIONS_TO_SCAN,
            )
            arxiv_publications = _filter_publications_with_abstract(refreshed_publications)
            if arxiv_publications:
                _upsert_cached_publications(
                    db=db,
                    profile_url=profile_url,
                    country=country,
                    professor_name=professor_name,
                    university_name=university_name,
                    publications=arxiv_publications,
                )
                logger.info(
                    "Cached ArXiv data for (%s, %s) pair (publications=%s)",
                    professor_name,
                    university_name or "",
                    len(arxiv_publications),
                )
            else:
                logger.info(
                    "Skipping ArXiv cache for (%s, %s): fetched publications had no usable abstracts",
                    professor_name,
                    university_name or "",
                )
        except Exception as exc:
            logger.warning("ArXiv research scraping failed for professor %s: %s", professor_name, exc)

    if arxiv_publications:
        matched = _semantic_match_publications(arxiv_publications, user_query=user_query)
        research_context = _format_research_context(matched, user_query=user_query)
        logger.info(
            "ArXiv research matching complete for professor %s (publications=%s, with_abstracts=%s, matched=%s)",
            professor_name,
            len(arxiv_publications),
            sum(1 for publication in arxiv_publications if publication.abstract),
            len(matched),
        )
        return research_context

    if professor_name:
        return f"No ArXiv publications found for {professor_name}."
    if profile_url:
        return f"No ArXiv publications found for profile {profile_url}."
    return "No ArXiv publications found for this candidate."
