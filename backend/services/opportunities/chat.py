import logging
import re
import uuid
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.opportunity_enums import OpportunityType, OpportunityStatus
from backend.infra.postgres.tables import Opportunity
from backend.services.users.settings import get_or_create_settings
from backend.services.admin.app_config import get_embedding_base_url
from backend.services.common.domain_errors import DomainValidationError
from backend.services.common.llm import LLMProvider, LLMProviderError, OllamaBackend
from backend.services.common.embeddings_generate import generate_embedding
from backend.services.opportunities.models import ChatContextItem, ChatServiceResult, ChatStreamPlan


logger = logging.getLogger(__name__)

_FREE_TIER_MAX_SEER_RECOMMENDATIONS = 5
_FREE_TIER_PROVIDER = "oppora_free"
_FREE_TIER_MODEL = "gemma4:31b-cloud"


def _enum_value(value: object) -> str:
    if isinstance(value, PyEnum):
        return str(value.value)
    return str(value)


def _tokenize_opportunity_terms(message: str) -> list[str]:
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this",
        "what", "tell", "about", "find", "show", "get", "all",
        "any", "are", "can", "hackathon", "hackathons", "opportunity", "opportunities",
    }
    terms: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"[a-zA-Z0-9]+", message.lower()):
        if len(term) < 3 or term in stopwords or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:8]


def _opportunity_ts(row: Opportunity) -> float:
    """Use the most relevant date for tiebreaking. Sooner deadline = ranked higher."""
    for dt in (row.deadline, row.end_date, row.start_date):
        if dt:
            return dt.timestamp()
    return 0.0


def _score_opportunity_rows_for_terms(row: Opportunity, terms: list[str]) -> int:
    if not terms:
        return 0

    title_hay = (row.title or "").lower()

    meta_hay = " ".join(filter(None, [
        row.source or "",
        row.mode or "",
        row.location or "",
        row.prize_money or "",
        row.team_size or "",
        " ".join(row.skills or []),
        " ".join(row.domains or []),
        " ".join(row.eligibility or []),
    ])).lower()

    body_hay = (row.description or "").lower()

    title_hits = sum(1 for term in terms if term in title_hay)
    meta_hits  = sum(1 for term in terms if term in meta_hay)
    body_hits  = sum(1 for term in terms if term in body_hay)

    return (title_hits * 4) + (meta_hits * 2) + body_hits


def _merge_context_rows(
    message: str,
    vector_rows: list[Opportunity],
    keyword_rows: list[Opportunity],
    limit: int,
) -> list[Opportunity]:
    terms = _tokenize_opportunity_terms(message)
    ranked: dict[uuid.UUID, tuple[Opportunity, int]] = {}

    for idx, row in enumerate(keyword_rows):
        keyword_rank = max(0, 240 - (idx * 8))
        term_bonus   = _score_opportunity_rows_for_terms(row, terms) * 20
        score        = keyword_rank + term_bonus
        existing     = ranked.get(row.id)
        if existing is None or score > existing[1]:
            ranked[row.id] = (row, score)

    for idx, row in enumerate(vector_rows):
        semantic_rank = max(0, 100 - (idx * 6))
        term_bonus    = _score_opportunity_rows_for_terms(row, terms) * 5
        score         = semantic_rank + term_bonus
        existing      = ranked.get(row.id)
        if existing is None:
            ranked[row.id] = (row, score)
        else:
            ranked[row.id] = (existing[0], existing[1] + score)

    merged = list(ranked.values())
    merged.sort(key=lambda entry: (entry[1], _opportunity_ts(entry[0])), reverse=True)
    return [row for row, _ in merged[:limit]]


def _keyword_opportunity_context_fallback(db: Session, message: str, limit: int) -> list[Opportunity]:
    terms = _tokenize_opportunity_terms(message)

    stmt: Select[tuple[Opportunity]] = select(Opportunity).where(
        Opportunity.opportunity_type == OpportunityType.Hackathon,
        Opportunity.status == OpportunityStatus.Active,
    )

    if terms:
        conditions = [
            or_(
                Opportunity.title.ilike(f"%{term}%"),
                Opportunity.description.ilike(f"%{term}%"),
                Opportunity.source.ilike(f"%{term}%"),
                Opportunity.mode.ilike(f"%{term}%"),
                Opportunity.location.ilike(f"%{term}%"),
                Opportunity.skills.any(term),
                Opportunity.domains.any(term),
                Opportunity.eligibility.any(term),
            )
            for term in terms
        ]
        stmt = stmt.where(or_(*conditions))

    fetch_limit = max(limit * 4, 12)
    rows = db.execute(
        stmt.order_by(
            Opportunity.deadline.asc().nullslast(),
            Opportunity.end_date.asc().nullslast(),
            Opportunity.created_at.desc(),
        ).limit(fetch_limit)
    ).scalars().all()

    return sorted(
        rows,
        key=lambda row: (_score_opportunity_rows_for_terms(row, terms), _opportunity_ts(row)),
        reverse=True,
    )[:limit]


def _retrieve_opportunity_context(db: Session, message: str, limit: int = 10) -> list[Opportunity]:
    has_embeddings = db.execute(
        select(Opportunity.id)
        .where(
            Opportunity.embedding.isnot(None),
            Opportunity.opportunity_type == OpportunityType.Hackathon,
            Opportunity.status == OpportunityStatus.Active,
        )
        .limit(1)
    ).first()

    if not has_embeddings:
        return _keyword_opportunity_context_fallback(db=db, message=message, limit=limit)

    base_url = get_embedding_base_url(db)
    try:
        query_embedding = generate_embedding(
            message, 
            base_url=base_url
        )
    except Exception as exc:
        logger.warning(
            "Opportunity embedding retrieval failed; falling back to keyword search: %s", 
            exc,
        )
        return _keyword_opportunity_context_fallback(db=db, message=message, limit=limit)

    stmt: Select[tuple[Opportunity]] = (
        select(Opportunity)
        .where(
            Opportunity.embedding.isnot(None),
            Opportunity.opportunity_type == OpportunityType.Hackathon,
            Opportunity.status == OpportunityStatus.Active,
        )
        .order_by(Opportunity.embedding.cosine_distance(query_embedding))
        .limit(max(limit, 12))
    )
    semantic_rows: list[Opportunity] = db.execute(stmt).scalars().all()
    keyword_rows = _keyword_opportunity_context_fallback(db=db, message=message, limit=max(limit, 12))

    if not semantic_rows:
        return keyword_rows[:limit]

    return _merge_context_rows(
        message=message,
        vector_rows=semantic_rows,
        keyword_rows=keyword_rows,
        limit=limit,
    )


def _format_opportunity_context(opportunities: list[Opportunity]) -> str:
    if not opportunities:
        return "No relevant opportunities were found in the database."

    lines: list[str] = []
    for idx, item in enumerate(opportunities, start=1):
        lines.append(f"{idx}. Title: {item.title}")
        lines.append(f"   Type: {_enum_value(item.opportunity_type)}")
        lines.append(f"   Source: {item.source}")
        lines.append(f"   Mode: {item.mode or 'unknown'}")
        lines.append(f"   Location: {item.location or 'unknown'}")
        lines.append(f"   Skills: {', '.join(item.skills or []) or 'unknown'}")
        lines.append(f"   Domains: {', '.join(item.domains or []) or 'unknown'}")
        lines.append(f"   Deadline: {item.deadline or 'unknown'}")
        lines.append(f"   Prize: {item.prize_money or 'unknown'}")
        lines.append(f"   URL: {item.url}")
        lines.append(f"   Description: {item.description or 'No description'}")
    return "\n".join(lines)


def _build_system_prompt(resume_text: str | None) -> str:
    base = (
        "You are a helpful assistant SeerAI for Oppora, an opportunity aggregator platform. "
        "Answer the user based only on the provided opportunities context. "
        "If the answer cannot be found in context, explicitly say that."
    )
    if resume_text:
        return (
            f"{base}\n\n"
            "The user has uploaded this resume:\n"
            "---\n"
            f"{resume_text}\n"
            "---\n"
            "Use resume details to personalize recommendations and explain why each match fits."
        )
    return base


def _format_conversation_history(history: list[dict[str, str]] | None) -> str:
    if not history:
        return "No previous conversation context."

    lines: list[str] = []
    for item in history[-8:]:
        role = item.get("role", "user").strip().lower()
        label = "User" if role == "user" else "Assistant"
        content = (item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{label}: {content}")

    return "\n".join(lines) if lines else "No previous conversation context."


def generate_opportunity_chat_response(
    db: Session,
    message: str,
    resume_text: str | None = None,
    user_id: UUID | None = None,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    use_free_tier: bool = False,
) -> ChatServiceResult:
    provider, system_prompt, user_prompt, context_items = _prepare_opportunity_chat_generation(
        db=db,
        message=message,
        resume_text=resume_text,
        user_id=user_id,
        preferred_provider=preferred_provider,
        preferred_model=preferred_model,
        conversation_history=conversation_history,
        use_free_tier=use_free_tier,
    )

    try:
        llm_result = provider.generate(user_prompt=user_prompt, system_prompt=system_prompt)
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"Chat provider failed: {exc}") from exc

    return ChatServiceResult(
        answer=llm_result.text,
        provider=llm_result.provider,
        model=llm_result.model,
        opportunities=context_items,
    )


def generate_opportunity_chat_response_stream(
    db: Session,
    message: str,
    resume_text: str | None = None,
    user_id: UUID | None = None,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    use_free_tier: bool = False,
) -> ChatStreamPlan:
    provider, system_prompt, user_prompt, context_items = _prepare_opportunity_chat_generation(
        db=db,
        message=message,
        resume_text=resume_text,
        user_id=user_id,
        preferred_provider=preferred_provider,
        preferred_model=preferred_model,
        conversation_history=conversation_history,
        use_free_tier=use_free_tier,
    )

    try:
        stream = provider.stream(user_prompt=user_prompt, system_prompt=system_prompt)
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"Chat provider failed: {exc}") from exc

    provider_name = getattr(provider, "provider_name", getattr(provider, "provider", "unknown"))
    model_name = getattr(provider, "model_name", getattr(provider, "model", "unknown"))

    return ChatStreamPlan(
        provider=provider_name,
        model=model_name,
        opportunities=context_items,
        stream=stream,
    )


def _prepare_opportunity_chat_generation(
    db: Session,
    message: str,
    resume_text: str | None,
    user_id: UUID | None,
    preferred_provider: str | None,
    preferred_model: str | None,
    conversation_history: list[dict[str, str]] | None,
    use_free_tier: bool,
) -> tuple[LLMProvider | OllamaBackend, str, str, list[ChatContextItem]]:
    if user_id is None:
        raise ValueError("user_id is required")

    settings = get_or_create_settings(db, user_id)
    opportunities_context = _retrieve_opportunity_context(db, message=message, limit=get_settings().chat_context_limit)
    logger.info("Chat context retrieval completed: opportunities=%s", len(opportunities_context))

    system_prompt = _build_system_prompt(resume_text)
    history_block = _format_conversation_history(conversation_history)
    user_prompt = (
        "Recent conversation (most recent turns):\n"
        f"{history_block}\n\n"
        f"User question:\n{message}\n\n"
        "Available opportunities:\n"
        f"{_format_opportunity_context(opportunities_context)}"
    )

    if use_free_tier:
        used = int(settings.free_seer_used or 0)
        if used >= _FREE_TIER_MAX_SEER_RECOMMENDATIONS:
            raise DomainValidationError("Free-tier SeerAI limit reached (5/5 used)")

        app_settings = get_settings()
        api_key = (app_settings.coldemail_profile_api_key or "").strip()
        if not api_key:
            raise DomainValidationError("Free-tier SeerAI is not configured. Set COLDEMAIL_PROFILE_API_KEY.")

        provider = OllamaBackend(
            model=_FREE_TIER_MODEL,
            base_url="https://api.ollama.com",
            provider_name=_FREE_TIER_PROVIDER,
            api_key=api_key,
            localhost_retry=False,
        )
    else:
        provider = LLMProvider(
            settings,
            preferred_provider=preferred_provider,
            preferred_model=preferred_model,
        )

    context_items = [
        ChatContextItem(
            id=item.id,
            title=item.title,
            url=item.url,
            opportunity_type=_enum_value(item.opportunity_type),
            source=item.source,
            status=_enum_value(item.status),
            deadline=item.deadline,
        )
        for item in opportunities_context
    ]

    return provider, system_prompt, user_prompt, context_items
