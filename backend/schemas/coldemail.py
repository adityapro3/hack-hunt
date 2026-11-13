from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


ASK_TYPE_VALUES = [
    "phd_inquiry",
    "research_assistant",
    "collaboration",
    "meeting_request",
    "internship_inquiry",
]


class ColdEmailStudentProject(BaseModel):
    title: str
    what: str
    impact: str | None = None


class ColdEmailStudentProfileData(BaseModel):
    full_name: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    projects: list[ColdEmailStudentProject] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    goal: str | None = None
    degree: str | None = None


class ColdEmailGenerateRequest(BaseModel):
    countries: list[str] = Field(min_length=1, max_length=10)
    website: str = "https://csrankings.org"
    tone: str = Field(default="professional", max_length=50)
    ask_type: str = Field(default="phd_inquiry", pattern="^(phd_inquiry|research_assistant|collaboration|meeting_request|internship_inquiry)$")
    max_professors: int = Field(default=5, ge=1, le=50)
    provider: str | None = None
    model: str | None = None
    use_free_tier: bool = False


class ColdEmailResumeParseRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)


class ColdEmailResumeParseResponse(BaseModel):
    filename: str
    resume_text: str


class ColdEmailSkillExtractRequest(BaseModel):
    resume_text: str = Field(min_length=20)
    provider: str | None = None
    model: str | None = None


class ColdEmailSkillExtractResponse(BaseModel):
    skills_text: str
    provider: str
    model: str


class ColdEmailProfileUpsertRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    allow_reupload: bool = False


class ColdEmailProfileResponse(BaseModel):
    user_id: UUID
    resume_filename: str | None = None
    profile: ColdEmailStudentProfileData
    profile_provider: str
    profile_model: str
    generated_at: datetime
    updated_at: datetime


class ColdEmailApproveRequest(BaseModel):
    recipient_email: str = Field(min_length=5, max_length=320)


class ColdEmailSendRequest(BaseModel):
    recipient_email: str | None = Field(default=None, min_length=5, max_length=320)


class ColdEmailResearchMatch(BaseModel):
    title: str
    similarity_score: float
    year: int | None = None
    url: str | None = None
    abstract: str | None = None


class ColdEmailDraftResponse(BaseModel):
    id: UUID
    country: str
    source: str
    professor_name: str
    university_name: str | None = None
    profile_url: str | None = None
    research_summary: str | None = None
    research_matches: list[ColdEmailResearchMatch] = Field(default_factory=list)
    subject_line: str
    body: str
    recipient_email: str | None = None
    tone: str
    ask_type: str
    provider: str
    model: str
    status: str
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


class ColdEmailListResponse(BaseModel):
    drafts: list[ColdEmailDraftResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
