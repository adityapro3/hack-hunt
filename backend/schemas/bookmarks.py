from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.schemas.opportunities import OpportunityResponse


class BookmarkCreateRequest(BaseModel):
    opportunity_id: UUID
    notes: str | None = None


class BookmarkResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    notes: str | None
    created_at: datetime
    opportunity: OpportunityResponse
