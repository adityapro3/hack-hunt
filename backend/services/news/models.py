from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Iterator

@dataclass
class NewsContextItem:
    id: UUID
    title: str
    source: str
    topic: str
    url: str
    published_at: datetime | None


@dataclass
class NewsChatServiceResult:
    answer: str
    provider: str
    model: str
    news: list[NewsContextItem]


@dataclass
class NewsChatStreamPlan:
    provider: str
    model: str
    news: list[NewsContextItem]
    stream: Iterator[str]
