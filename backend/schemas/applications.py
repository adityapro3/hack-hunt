from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.schemas.opportunities import OpportunityResponse


class ApplicationCreateRequest(BaseModel):
    opportunity_id: UUID
    status: str = "interested"
    applied_at: datetime | None = None
    notes: str | None = None


class ApplicationUpdateRequest(BaseModel):
    status: str | None = None
    applied_at: datetime | None = None
    notes: str | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    status: str
    applied_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    opportunity: OpportunityResponse
