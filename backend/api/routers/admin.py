from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from backend.infra.postgres.session import SessionLocal, get_db
from backend.api.deps.auth import get_current_admin_user
from backend.infra.postgres.tables import User, Opportunity, NewsArticle
from backend.schemas import (
    EmbeddingBackfillResponse,
    EmbeddingTargetBackfillRequest,
    ExpiredCleanupRequest,
    ExpiredCleanupResponse,
    NewsTopicBackfillRequest,
    NewsTopicBackfillResponse,
    NewsScrapeRunRequest,
    NewsScrapeRunResponse,
    ScraperSourcesResponse,
    ScraperRunRequest,
    ScraperRunResponse,
)

from backend.services.admin import (
    SCRAPER_REGISTRY,
    run_selected_scrapers,
    run_news_latest_scraping, 
    run_embedding_backfill,
    run_news_topic_backfill,
    run_expired_cleanup,
)
from backend.services.admin.logs_streaming import stream_admin_job

router = APIRouter(prefix="/api/scraper", tags=["scraper"])


@router.get("/available", response_model=ScraperSourcesResponse)
def list_available_scrapers(_admin: User = Depends(get_current_admin_user)):
    return ScraperSourcesResponse(scrapers=sorted(SCRAPER_REGISTRY.keys()))


@router.post("/opportunities/run", response_model=ScraperRunResponse)
async def run_scraper(
    payload: ScraperRunRequest,
    _admin: User = Depends(get_current_admin_user),
):
    result = await run_selected_scrapers(payload.sources)
    return ScraperRunResponse(**result)


@router.post("/opportunities/run/stream")
async def run_scraper_stream(
    payload: ScraperRunRequest,
    _admin: User = Depends(get_current_admin_user),
):
    return stream_admin_job(
        "hackathon scrapers",
        lambda emit_log: run_selected_scrapers(payload.sources, emit_log=emit_log),
    )


@router.post("/news/run", response_model=NewsScrapeRunResponse)
async def run_news_scrapers(
    payload: NewsScrapeRunRequest,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    result = await run_news_latest_scraping(
        db=db,
        sources=payload.sources,
        max_pages_per_source=payload.max_pages_per_source,
        keep_days=payload.keep_days,
    )
    return NewsScrapeRunResponse(**result)


@router.post("/news/run/stream")
async def run_news_scrapers_stream(
    payload: NewsScrapeRunRequest,
    _admin: User = Depends(get_current_admin_user),
):
    def job(emit_log):
        with SessionLocal() as db:
            return run_news_latest_scraping(
                db=db,
                sources=payload.sources,
                max_pages_per_source=payload.max_pages_per_source,
                keep_days=payload.keep_days,
                emit_log=emit_log,
            )

    return stream_admin_job("news scrapers", job)


@router.post("/embeddings/backfill/opportunities", response_model=EmbeddingBackfillResponse)
def backfill_opportunity_embeddings(
    payload: EmbeddingTargetBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    result = run_embedding_backfill(
        db=db,
        model_class=Opportunity,
        batch_size=payload.batch_size,
        source=payload.source,
        run_until_empty=payload.run_until_empty,
    )
    return EmbeddingBackfillResponse(**result)


@router.post("/embeddings/backfill/opportunities/stream")
def backfill_opportunity_embeddings_stream(
    payload: EmbeddingTargetBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
):
    def job(emit_log):
        with SessionLocal() as db:
            return run_embedding_backfill(
                db=db,
                model_class=Opportunity,
                batch_size=payload.batch_size,
                source=payload.source,
                run_until_empty=payload.run_until_empty,
                emit_log=emit_log,
            )

    return stream_admin_job("opportunity embeddings", job)


@router.post("/embeddings/backfill/news", response_model=EmbeddingBackfillResponse)
def backfill_news_embeddings(
    payload: EmbeddingTargetBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    result = run_embedding_backfill(
        db=db,
        model_class=NewsArticle,
        batch_size=payload.batch_size,
        source=payload.source,
        run_until_empty=payload.run_until_empty,
    )
    return EmbeddingBackfillResponse(**result)


@router.post("/embeddings/backfill/news/stream")
def backfill_news_embeddings_stream(
    payload: EmbeddingTargetBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
):
    def job(emit_log):
        with SessionLocal() as db:
            return run_embedding_backfill(
                db=db,
                model_class=NewsArticle,
                batch_size=payload.batch_size,
                source=payload.source,
                run_until_empty=payload.run_until_empty,
                emit_log=emit_log,
            )

    return stream_admin_job("news embeddings", job)


@router.post("/topics/backfill/news", response_model=NewsTopicBackfillResponse)
def backfill_news_topics(
    payload: NewsTopicBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    result = run_news_topic_backfill(
        db=db,
        batch_size=payload.batch_size,
        source=payload.source,
        run_until_empty=payload.run_until_empty,
        overwrite_existing=payload.overwrite_existing,
    )
    return NewsTopicBackfillResponse(**result)


@router.post("/topics/backfill/news/stream")
def backfill_news_topics_stream(
    payload: NewsTopicBackfillRequest,
    _admin: User = Depends(get_current_admin_user),
):
    def job(emit_log):
        with SessionLocal() as db:
            return run_news_topic_backfill(
                db=db,
                batch_size=payload.batch_size,
                source=payload.source,
                run_until_empty=payload.run_until_empty,
                overwrite_existing=payload.overwrite_existing,
                emit_log=emit_log,
            )

    return stream_admin_job("news topic backfill", job)


@router.post("/cleanup/expired", response_model=ExpiredCleanupResponse)
def cleanup_expired(
    payload: ExpiredCleanupRequest = ExpiredCleanupRequest(),
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    result = run_expired_cleanup(db=db, news_keep_days=payload.news_keep_days)
    return ExpiredCleanupResponse(**result)
