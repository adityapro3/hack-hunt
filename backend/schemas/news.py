from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NewsArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    topic: str
    title: str
    url: str
    content: str
    language: str
    published_at: datetime | None = None
    scraped_at: datetime
    created_at: datetime


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int


class NewsFiltersResponse(BaseModel):
    topics: list[str] = Field(default_factory=list)


class NewsScrapeRunRequest(BaseModel):
    sources: list[str] = Field(default_factory=list)
    max_pages_per_source: int = Field(default=12, ge=1, le=50)
    keep_days: int = Field(default=3, ge=1, le=7)


class NewsScrapeRunResponse(BaseModel):
    total_scraped: int
    total_saved: int
    by_source: dict[str, int] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    max_pages_per_source: int
    keep_days: int
    logs: list[str] = Field(default_factory=list)


class NewsChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)


class NewsChatContextItem(BaseModel):
    id: UUID
    title: str
    source: str
    topic: str
    url: str
    published_at: datetime | None = None


class NewsChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    retrieved_count: int
    context: list[NewsChatContextItem] = Field(default_factory=list)
