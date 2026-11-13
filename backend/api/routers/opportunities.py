from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
import json

from backend.api.deps.auth import get_current_user
from backend.core.opportunity_enums import parse_opportunity_status, parse_opportunity_type
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User
from backend.schemas import (
    ChatContextOpportunity,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatThreadCreateRequest,
    ChatThreadSummaryResponse,
    OpportunityFiltersResponse,
    OpportunityResponse,
)
from backend.services.common.ai_errors import LLMProviderError
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError
from backend.services.opportunities.chat import (
    generate_opportunity_chat_response,
    generate_opportunity_chat_response_stream,
)
from backend.services.opportunities.query import (
    get_opportunity_filters,
    get_opportunity_or_raise,
    list_opportunities as list_opportunities_service,
)
from backend.services.opportunities.thread import (
    create_thread_for_user,
    delete_thread_for_user,
    get_or_create_thread_for_message,
    get_thread_for_user_or_raise,
    list_messages_for_thread,
    list_threads_for_user,
    load_recent_history,
    save_chat_exchange,
)
from backend.services.users.settings import get_or_create_settings

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


def _serialize_context(opportunities: list[ChatContextOpportunity]) -> list[dict]:
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "url": item.url,
            "opportunity_type": str(item.opportunity_type),
            "source": item.source,
            "status": str(item.status),
            "deadline": item.deadline.isoformat() if item.deadline else None,
        }
        for item in opportunities
    ]


def _deserialize_context(raw: list[dict] | None) -> list[ChatContextOpportunity]:
    items = raw or []
    parsed: list[ChatContextOpportunity] = []
    for item in items:
        parsed.append(
            ChatContextOpportunity(
                id=item.get("id"),
                title=item.get("title") or "",
                url=item.get("url") or "",
                opportunity_type=parse_opportunity_type(item.get("opportunity_type")),
                source=item.get("source") or "",
                status=parse_opportunity_status(item.get("status")),
                deadline=item.get("deadline"),
            )
        )
    return parsed

@router.get("", response_model=list[OpportunityResponse])
def list_opportunities(
    opportunity_type: str | None = Query(default=None, alias="type"),
    mode: str | None = None,
    domain: str | None = None,
    skill: str | None = None,
    status: str | None = None,
    source: str | None = None,
    sort: str = "deadline",
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return list_opportunities_service(
        db=db,
        opportunity_type=opportunity_type,
        mode=mode,
        domain=domain,
        skill=skill,
        status=status,
        source=source,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/filters", response_model=OpportunityFiltersResponse)
def get_filters(
    opportunity_type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
):
    payload = get_opportunity_filters(db=db, opportunity_type=opportunity_type)
    return OpportunityFiltersResponse(**payload)


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(opportunity_id: UUID, db: Session = Depends(get_db)):
    try:
        return get_opportunity_or_raise(db=db, opportunity_id=opportunity_id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --- Chat Endpoints ---

@router.get("/chat/threads", response_model=list[ChatThreadSummaryResponse])
def list_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_threads_for_user(db=db, user_id=current_user.id, limit=100)
    return [ChatThreadSummaryResponse(**row) for row in rows]


@router.post("/chat/threads", response_model=ChatThreadSummaryResponse)
def create_thread(
    payload: ChatThreadCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = create_thread_for_user(db=db, user_id=current_user.id, title=payload.title)

    return ChatThreadSummaryResponse(
        id=thread.id,
        title=thread.title,
        message_count=0,
        last_message_preview=None,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.delete("/chat/threads/{thread_id}", status_code=204)
def delete_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_thread_for_user(db=db, thread_id=thread_id, user_id=current_user.id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessageResponse])
def list_thread_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        get_thread_for_user_or_raise(db=db, thread_id=thread_id, user_id=current_user.id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rows = list_messages_for_thread(db=db, thread_id=thread_id)

    return [
        ChatMessageResponse(
            id=row.id,
            thread_id=row.thread_id,
            role=row.role,
            content=row.content,
            provider=row.provider,
            model=row.model,
            context=_deserialize_context(row.context),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/chat", response_model=ChatResponse)
def chat_opportunity(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        thread = get_or_create_thread_for_message(
            db=db,
            user_id=current_user.id,
            thread_id=payload.thread_id,
            message=payload.message,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = load_recent_history(db=db, thread_id=thread.id, limit=8)

    try:
        result = generate_opportunity_chat_response(
            db,
            message=payload.message,
            resume_text=payload.resume_text,
            user_id=current_user.id,
            preferred_provider=payload.provider,
            preferred_model=payload.model,
            conversation_history=history,
            use_free_tier=payload.use_free_tier,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    assistant_context = [
        ChatContextOpportunity(
            id=item.id,
            title=item.title,
            url=item.url,
            opportunity_type=item.opportunity_type,
            source=item.source,
            status=item.status,
            deadline=item.deadline,
        )
        for item in result.opportunities
    ]

    save_chat_exchange(
        db=db,
        thread=thread,
        user_message=payload.message,
        assistant_message=result.answer,
        provider=result.provider,
        model=result.model,
        context=_serialize_context(assistant_context),
    )

    if payload.use_free_tier:
        user_settings = get_or_create_settings(db, current_user.id)
        user_settings.free_seer_used = int(user_settings.free_seer_used or 0) + 1
        db.commit()

    return ChatResponse(
        answer=result.answer,
        provider=result.provider,
        model=result.model,
        thread_id=thread.id,
        retrieved_count=len(result.opportunities),
        opportunities=assistant_context,
    )


@router.post("/chat/stream")
def chat_opportunity_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        thread = get_or_create_thread_for_message(
            db=db,
            user_id=current_user.id,
            thread_id=payload.thread_id,
            message=payload.message,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = load_recent_history(db=db, thread_id=thread.id, limit=8)

    try:
        plan = generate_opportunity_chat_response_stream(
            db,
            message=payload.message,
            resume_text=payload.resume_text,
            user_id=current_user.id,
            preferred_provider=payload.provider,
            preferred_model=payload.model,
            conversation_history=history,
            use_free_tier=payload.use_free_tier,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    assistant_context = [
        ChatContextOpportunity(
            id=item.id,
            title=item.title,
            url=item.url,
            opportunity_type=item.opportunity_type,
            source=item.source,
            status=item.status,
            deadline=item.deadline,
        )
        for item in plan.opportunities
    ]

    def _event_stream():
        meta_event = {
            "type": "meta",
            "thread_id": str(thread.id),
            "provider": plan.provider,
            "model": plan.model,
            "retrieved_count": len(assistant_context),
            "opportunities": _serialize_context(assistant_context),
        }
        yield json.dumps(meta_event) + "\n"

        chunks: list[str] = []
        try:
            for delta in plan.stream:
                if not delta:
                    continue
                chunks.append(delta)
                yield json.dumps({"type": "delta", "content": delta}) + "\n"
        except LLMProviderError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
            return
        except Exception as exc:
            yield json.dumps({"type": "error", "detail": f"Chat stream failed: {exc}"}) + "\n"
            return

        answer = "".join(chunks).strip()
        if not answer:
            yield json.dumps({"type": "error", "detail": "Provider returned an empty response"}) + "\n"
            return

        save_chat_exchange(
            db=db,
            thread=thread,
            user_message=payload.message,
            assistant_message=answer,
            provider=plan.provider,
            model=plan.model,
            context=_serialize_context(assistant_context),
        )

        if payload.use_free_tier:
            user_settings = get_or_create_settings(db, current_user.id)
            user_settings.free_seer_used = int(user_settings.free_seer_used or 0) + 1
            db.commit()

        done_event = {
            "type": "done",
            "thread_id": str(thread.id),
            "provider": plan.provider,
            "model": plan.model,
            "answer": answer,
            "retrieved_count": len(assistant_context),
            "opportunities": _serialize_context(assistant_context),
        }
        yield json.dumps(done_event) + "\n"

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")
