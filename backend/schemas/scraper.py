from datetime import datetime

from pydantic import BaseModel, Field


class ScraperRunRequest(BaseModel):
    sources: list[str] = Field(default_factory=list)


class ScraperRunResponse(BaseModel):
    total_scraped: int
    total_saved: int
    by_source: dict[str, int]
    logs: list[str] = Field(default_factory=list)


class ScraperSourcesResponse(BaseModel):
    scrapers: list[str]


class EmbeddingTargetBackfillRequest(BaseModel):
    batch_size: int = Field(default=50, ge=1, le=500)
    source: str | None = None
    run_until_empty: bool = False


class EmbeddingBackfillResponse(BaseModel):
    processed: int
    failed: int
    remaining: int
    batches_ran: int = 0
    source: str | None = None
    logs: list[str] = Field(default_factory=list)


class NewsTopicBackfillRequest(BaseModel):
    batch_size: int = Field(default=50, ge=1, le=500)
    source: str | None = None
    run_until_empty: bool = False
    overwrite_existing: bool = False


class NewsTopicBackfillResponse(BaseModel):
    processed: int
    failed: int
    remaining: int
    batches_ran: int = 0
    source: str | None = None
    logs: list[str] = Field(default_factory=list)


class ExpiredCleanupResponse(BaseModel):
    matched: int
    deleted: int
    opportunity_matched: int = 0
    opportunity_deleted: int = 0
    news_matched: int = 0
    news_deleted: int = 0
    news_keep_days: int = 3
    now_utc: datetime


class ExpiredCleanupRequest(BaseModel):
    news_keep_days: int = Field(default=3, ge=1, le=30)
