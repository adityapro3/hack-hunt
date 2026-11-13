import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps.auth import get_current_user
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User
from backend.schemas import (
    ColdEmailDraftResponse,
    ColdEmailGenerateRequest,
    ColdEmailListResponse,
    ColdEmailProfileResponse,
    ColdEmailProfileUpsertRequest,
    ColdEmailResumeParseRequest,
    ColdEmailResumeParseResponse,
    ColdEmailSkillExtractRequest,
    ColdEmailSkillExtractResponse,
    ColdEmailApproveRequest,
    ColdEmailSendRequest,
)
from backend.services.common.ai_errors import LLMProviderError
from backend.services.coldemail import (
    extract_skills_from_resume,
    get_user_coldemail_profile,
    generate_cold_email_event_stream,
    list_cold_email_drafts,
    parse_resume_content,
    serialize_draft,
    upsert_user_coldemail_profile,
    approve_cold_email_draft,
    delete_cold_email_draft,
    send_cold_email_draft,
)
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError


router = APIRouter(prefix="/api/coldemail", tags=["coldemail"])


def _serialize_profile(row) -> ColdEmailProfileResponse:
    return ColdEmailProfileResponse(
        user_id=row.user_id,
        resume_filename=row.resume_filename,
        profile=row.profile_json or {},
        profile_provider=row.profile_provider,
        profile_model=row.profile_model,
        generated_at=row.generated_at,
        updated_at=row.updated_at,
    )


@router.get("/drafts", response_model=ColdEmailListResponse)
def list_drafts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total_count = list_cold_email_drafts(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return ColdEmailListResponse(
        drafts=[serialize_draft(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.post("/generate/stream")
async def generate_stream(
    payload: ColdEmailGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        stream = generate_cold_email_event_stream(
            db=db,
            user_id=current_user.id,
            payload=payload,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    async def _event_stream():
        try:
            async for event in stream:
                yield json.dumps(event) + "\n"
        except DomainValidationError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
        except LLMProviderError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "detail": f"Cold-email generation failed: {exc}"}) + "\n"

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")


@router.post("/resume/parse", response_model=ColdEmailResumeParseResponse)
def parse_resume(
    payload: ColdEmailResumeParseRequest,
    _current_user: User = Depends(get_current_user),
):
    try:
        resume_text = parse_resume_content(
            filename=payload.filename,
            content_base64=payload.content_base64,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ColdEmailResumeParseResponse(
        filename=payload.filename,
        resume_text=resume_text,
    )


@router.get("/profile", response_model=ColdEmailProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_user_coldemail_profile(db=db, user_id=current_user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cold-email profile not found")
    return _serialize_profile(row)


@router.post("/profile", response_model=ColdEmailProfileResponse)
def upsert_profile(
    payload: ColdEmailProfileUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = upsert_user_coldemail_profile(
            db=db,
            user_id=current_user.id,
            filename=payload.filename,
            content_base64=payload.content_base64,
            allow_reupload=payload.allow_reupload,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _serialize_profile(row)


@router.post("/skills/extract", response_model=ColdEmailSkillExtractResponse)
def extract_skills(
    payload: ColdEmailSkillExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = extract_skills_from_resume(
            db=db,
            user_id=current_user.id,
            resume_text=payload.resume_text,
            preferred_provider=payload.provider,
            preferred_model=payload.model,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ColdEmailSkillExtractResponse(**result)


@router.patch("/drafts/{draft_id}/approve", response_model=ColdEmailDraftResponse)
def approve_draft(
    draft_id: UUID,
    payload: ColdEmailApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = approve_cold_email_draft(
            db=db,
            user_id=current_user.id,
            draft_id=draft_id,
            recipient_email=payload.recipient_email,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return serialize_draft(row)


@router.post("/drafts/{draft_id}/send", response_model=ColdEmailDraftResponse)
def send_draft(
    draft_id: UUID,
    payload: ColdEmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = send_cold_email_draft(
            db=db,
            user_id=current_user.id,
            draft_id=draft_id,
            recipient_email=payload.recipient_email,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return serialize_draft(row)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_cold_email_draft(
            db=db,
            user_id=current_user.id,
            draft_id=draft_id,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
