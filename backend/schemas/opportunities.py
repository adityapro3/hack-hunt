from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.core.opportunity_enums import OpportunityStatus, OpportunityType


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opportunity_type: OpportunityType
    title: str
    url: str
    source: str
    description: str | None
    domains: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mode: str | None
    location: str | None
    start_date: datetime | None
    end_date: datetime | None
    deadline: datetime | None
    prize_money: str | None
    registration_fee: str | None
    team_size: str | None
    eligibility: list[str] = Field(default_factory=list)
    status: OpportunityStatus
    created_at: datetime


class OpportunityFiltersResponse(BaseModel):
    types: list[OpportunityType]
    domains: list[str]
    skills: list[str]
    modes: list[str]
    statuses: list[OpportunityStatus]
    sources: list[str]
