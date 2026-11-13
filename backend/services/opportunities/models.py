from dataclasses import dataclass
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID


@dataclass
class ChatContextItem:
    id: UUID
    title: str
    url: str
    opportunity_type: str
    source: str
    status: str
    deadline: datetime | None


@dataclass
class ChatServiceResult:
    answer: str
    provider: str
    model: str
    opportunities: list[ChatContextItem]


@dataclass
class ChatStreamPlan:
    provider: str
    model: str
    opportunities: list[ChatContextItem]
    stream: Iterator[str]
