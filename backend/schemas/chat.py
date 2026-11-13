from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from backend.core.opportunity_enums import OpportunityStatus, OpportunityType


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    resume_text: str | None = None
    provider: str | None = None
    model: str | None = None
    use_free_tier: bool = False
    thread_id: UUID | None = None


class ChatThreadCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatThreadSummaryResponse(BaseModel):
    id: UUID
    title: str
    message_count: int
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatContextOpportunity(BaseModel):
    id: UUID
    title: str
    url: str
    opportunity_type: OpportunityType
    source: str
    status: OpportunityStatus
    deadline: datetime | None


class ChatMessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: str
    content: str
    provider: str | None = None
    model: str | None = None
    context: list[ChatContextOpportunity] = Field(default_factory=list)
    created_at: datetime


class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    thread_id: UUID
    retrieved_count: int
    opportunities: list[ChatContextOpportunity] = Field(default_factory=list)
