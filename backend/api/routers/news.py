from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from backend.api.deps.auth import get_current_user
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User
from backend.schemas.news import (
    NewsArticleResponse,
    NewsChatContextItem,
    NewsChatRequest,
    NewsChatResponse,
    NewsFiltersResponse,
    NewsListResponse,
)
from backend.services.common.ai_errors import LLMProviderError
from backend.services.news import (
    generate_news_chat_response,
    generate_news_chat_response_stream,
)
from backend.services.news.query import (
    list_news_articles, 
    get_news_filters,
)


router = APIRouter(prefix="/api/news", tags=["news"])


def _sse_data(payload: object) -> str:
    return f"data: {json.dumps(jsonable_encoder(payload))}\n\n"


@router.get("", response_model=NewsListResponse)
def list_news(
    topic: str | None = None,
    q: str | None = Query(default=None, max_length=200),
    semantic: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total_count = list_news_articles(
        db=db,
        topic=topic,
        q=q,
        semantic=semantic,
        limit=limit,
        offset=offset,
    )
    return NewsListResponse(
        items=[NewsArticleResponse.model_validate(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/filters", response_model=NewsFiltersResponse)
def list_news_filter_values(db: Session = Depends(get_db)):
    payload = get_news_filters(db)
    return NewsFiltersResponse(**payload)


@router.post("/chat", response_model=NewsChatResponse)
def chat_over_news(
    payload: NewsChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = generate_news_chat_response(
            db=db,
            user_id=current_user.id,
            message=payload.message,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return NewsChatResponse(
        answer=result.answer,
        provider=result.provider,
        model=result.model,
        retrieved_count=len(result.news),
        context=[NewsChatContextItem.model_validate(item.__dict__) for item in result.news],
    )


@router.post("/chat/stream")
def chat_over_news_stream(
    payload: NewsChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        plan = generate_news_chat_response_stream(
            db=db,
            user_id=current_user.id,
            message=payload.message,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    context_items = [NewsChatContextItem.model_validate(item.__dict__) for item in plan.news]

    def _event_stream():
        meta_event = {
            "type": "meta",
            "provider": plan.provider,
            "model": plan.model,
            "retrieved_count": len(context_items),
            "context": [item.model_dump(mode="json") for item in context_items],
        }
        yield _sse_data(meta_event)

        for chunk in plan.stream:
            yield _sse_data({"type": "content", "delta": chunk})

        yield _sse_data({"type": "done"})

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
