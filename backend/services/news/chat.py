import logging
import re
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.infra.postgres.tables import NewsArticle
from backend.services.common.llm import OllamaBackend
from backend.services.common.ai_errors import LLMProviderError
from backend.services.admin.app_config import get_embedding_base_url
from backend.services.common.embeddings_generate import generate_embedding
from backend.services.news.models import NewsContextItem, NewsChatServiceResult, NewsChatStreamPlan


logger = logging.getLogger(__name__)

_FREE_TIER_PROVIDER = "oppora_free"
_FREE_TIER_MODEL = "gemma4:31b-cloud"


def _tokenize_query_terms(message: str) -> list[str]:
    stopwords = {
        "the", "and", "for", "with",
        "from", "that", "this", "what",
        "tell", "about", "news", "latest", "today",
    }
    terms: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"[a-zA-Z0-9]+", message.lower()):
        if len(term) < 2 or term in stopwords or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:12]


def _published_ts(row: NewsArticle) -> float:
    if not row.published_at:
        return 0.0
    return row.published_at.timestamp()


def _score_news_rows_for_terms(row: NewsArticle, terms: list[str]) -> int:
    if not terms:
        return 0

    title_hay = (row.title or "").lower()
    meta_hay = f"{row.topic or ''} {row.source or ''}".lower()
    body_hay = (row.content or "").lower()

    title_hits = sum(1 for term in terms if term in title_hay)
    meta_hits = sum(1 for term in terms if term in meta_hay)
    body_hits = sum(1 for term in terms if term in body_hay)

    # Prefer direct title/meta hits; body-only hits are weaker.
    return (title_hits * 4) + (meta_hits * 2) + body_hits


def _merge_context_rows(
    message: str,
    vector_rows: list[NewsArticle],
    keyword_rows: list[NewsArticle],
    limit: int,
) -> list[NewsArticle]:
    terms = _tokenize_query_terms(message)
    ranked: dict[UUID, tuple[NewsArticle, int]] = {}

    for idx, row in enumerate(keyword_rows):
        keyword_rank = max(0, 240 - (idx * 8))
        term_bonus = _score_news_rows_for_terms(row, terms) * 20
        score = keyword_rank + term_bonus
        existing = ranked.get(row.id)
        if existing is None or score > existing[1]:
            ranked[row.id] = (row, score)

    for idx, row in enumerate(vector_rows):
        semantic_rank = max(0, 100 - (idx * 6))
        term_bonus = _score_news_rows_for_terms(row, terms) * 5
        score = semantic_rank + term_bonus
        existing = ranked.get(row.id)
        if existing is None:
            ranked[row.id] = (row, score)
        else:
            ranked[row.id] = (existing[0], existing[1] + score)

    merged = [item for item in ranked.values()]
    merged.sort(key=lambda entry: (entry[1], _published_ts(entry[0])), reverse=True)
    return [row for row, _ in merged[:limit]]


def _keyword_news_context_fallback(db: Session, message: str, limit: int) -> list[NewsArticle]:
    terms = _tokenize_query_terms(message)

    stmt: Select[tuple[NewsArticle]] = select(NewsArticle)
    if terms:
        conditions = [
            or_(
                NewsArticle.title.ilike(f"%{term}%"),
                NewsArticle.content.ilike(f"%{term}%"),
                NewsArticle.topic.ilike(f"%{term}%"),
                NewsArticle.source.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        stmt = stmt.where(or_(*conditions))

    fetch_limit = max(limit * 4, limit)
    rows = db.execute(
        stmt.order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.created_at.desc()).limit(fetch_limit)
    ).scalars().all()

    ranked_rows = sorted(
        rows,
        key=lambda row: (_score_news_rows_for_terms(row, terms), _published_ts(row)),
        reverse=True,
    )
    return ranked_rows[:limit]


def _retrieve_news_context(db: Session, message: str, limit: int = 8) -> list[NewsArticle]:
    has_embeddings = db.execute(
        select(NewsArticle.id)
        .where(NewsArticle.embedding.isnot(None))
        .limit(1)
    ).first()
    if not has_embeddings:
        return _keyword_news_context_fallback(db=db, message=message, limit=limit)

    base_url = get_embedding_base_url(db)
    try:
        query_embedding = generate_embedding(
            message,
            base_url=base_url,
        )
    except Exception as exc:
        logger.warning(
            "News chatbot embedding retrieval failed; falling back to keyword context: %s",
            exc,
        )
        return _keyword_news_context_fallback(db=db, message=message, limit=limit)

    stmt: Select[tuple[NewsArticle]] = (
        select(NewsArticle)
        .where(NewsArticle.embedding.isnot(None))
        .order_by(NewsArticle.embedding.cosine_distance(query_embedding))
        .limit(max(limit, 12))
    )
    semantic_rows = db.execute(stmt).scalars().all()
    keyword_rows = _keyword_news_context_fallback(db=db, message=message, limit=max(limit, 12))

    if not semantic_rows:
        return keyword_rows[:limit]
    return _merge_context_rows(message=message, vector_rows=semantic_rows, keyword_rows=keyword_rows, limit=limit)


def _format_news_context(rows: list[NewsArticle]) -> str:
    if not rows:
        return "No relevant news articles were found."

    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        snippet = re.sub(r"\s+", " ", (row.content or "")).strip()
        if len(snippet) > 650:
            snippet = snippet[:650] + "..."

        lines.append(f"{idx}. Title: {row.title}")
        lines.append(f"   Source: {row.source}")
        lines.append(f"   Published: {row.published_at or 'unknown'}")
        lines.append(f"   Excerpt: {snippet or 'No excerpt available'}")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return (
        "You are a focused news assistant ScrollAI inside Oppora. "
        "Answer using ONLY the provided news context & what exactly user wants. "
        "Summarize atleast 3 most relevant news articles from the context in your answer. "
        "If context is missing, explicitly say so and do not invent facts. "
        "When helpful, cite source names and article titles briefly."
    )


def generate_news_chat_response(
    db: Session,
    user_id: UUID,
    message: str,
) -> NewsChatServiceResult:
    backend, system_prompt, user_prompt, context_items = _prepare_news_chat_generation(
        db=db,
        user_id=user_id,
        message=message,
    )

    try:
        result = backend.generate(user_prompt=user_prompt, system_prompt=system_prompt)
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"News chat provider failed: {exc}") from exc

    return NewsChatServiceResult(
        answer=result.text,
        provider=result.provider,
        model=result.model,
        news=context_items,
    )


def generate_news_chat_response_stream(
    db: Session,
    user_id: UUID,
    message: str,
) -> NewsChatStreamPlan:
    provider, system_prompt, user_prompt, context_items = _prepare_news_chat_generation(
        db=db,
        user_id=user_id,
        message=message,
    )

    try:
        stream = provider.stream(user_prompt=user_prompt, system_prompt=system_prompt)
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"News chat provider failed: {exc}") from exc

    return NewsChatStreamPlan(
        provider=provider.provider,
        model=provider.model,
        news=context_items,
        stream=stream,
    )


def _prepare_news_chat_generation(
    db: Session,
    user_id: UUID,
    message: str,
) -> tuple[OllamaBackend, str, str, list[NewsContextItem]]:
    _ = user_id
    news_context = _retrieve_news_context(db=db, message=message, limit=8)

    app_settings = get_settings()
    api_key = (app_settings.coldemail_profile_api_key or "").strip()
    if not api_key:
        raise LLMProviderError(
            "ScrollAI is not configured. Set COLDEMAIL_PROFILE_API_KEY for Ollama Cloud access."
        )

    provider = OllamaBackend(
        model=_FREE_TIER_MODEL,
        base_url="https://api.ollama.com",
        provider_name=_FREE_TIER_PROVIDER,
        api_key=api_key,
        localhost_retry=False,
    )

    system_prompt = _build_system_prompt()

    user_prompt = (
        "User question:\n"
        f"{message.strip()}\n\n"
        "Available news context:\n"
        f"{_format_news_context(news_context)}"
    )

    context_items = [
        NewsContextItem(
            id=row.id,
            title=row.title,
            source=row.source,
            topic=row.topic,
            url=row.url,
            published_at=row.published_at,
        )
        for row in news_context
    ]

    return provider, system_prompt, user_prompt, context_items
