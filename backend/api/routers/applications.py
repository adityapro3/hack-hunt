from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps.auth import get_current_user
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import Application, Opportunity, User
from backend.schemas import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationUpdateRequest,
    OpportunityResponse,
)
from backend.services.users.applications import (
    create_or_update_application,
    delete_user_application,
    list_user_applications,
    update_user_application,
)
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _to_response(application: Application, opportunity: Opportunity) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        opportunity_id=application.opportunity_id,
        status=application.status,
        applied_at=application.applied_at,
        notes=application.notes,
        created_at=application.created_at,
        updated_at=application.updated_at,
        opportunity=OpportunityResponse.model_validate(opportunity),
    )


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    opportunity_type: str | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        rows = list_user_applications(
            db=db,
            user_id=current_user.id,
            opportunity_type=opportunity_type,
            status_filter=status_filter,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [_to_response(application, opportunity) for application, opportunity in rows]


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        application, opportunity = create_or_update_application(
            db=db,
            user_id=current_user.id,
            opportunity_id=payload.opportunity_id,
            status=payload.status,
            applied_at=payload.applied_at,
            notes=payload.notes,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_response(application, opportunity)


@router.put("/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: UUID,
    payload: ApplicationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        application, opportunity = update_user_application(
            db=db,
            user_id=current_user.id,
            application_id=application_id,
            status=payload.status,
            applied_at=payload.applied_at,
            notes=payload.notes,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_response(application, opportunity)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_user_application(db=db, user_id=current_user.id, application_id=application_id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
