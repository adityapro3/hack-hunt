from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps.auth import get_current_user
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import Bookmark, Opportunity, User
from backend.schemas import BookmarkCreateRequest, BookmarkResponse, OpportunityResponse
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError
from backend.services.users.bookmarks import create_or_update_bookmark, delete_user_bookmark, list_user_bookmarks

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


def _to_response(bookmark: Bookmark, opportunity: Opportunity) -> BookmarkResponse:
    return BookmarkResponse(
        id=bookmark.id,
        opportunity_id=bookmark.opportunity_id,
        notes=bookmark.notes,
        created_at=bookmark.created_at,
        opportunity=OpportunityResponse.model_validate(opportunity),
    )


@router.get("", response_model=list[BookmarkResponse])
def list_bookmarks(
    opportunity_type: str | None = Query(default=None, alias="type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_user_bookmarks(
        db=db,
        user_id=current_user.id,
        opportunity_type=opportunity_type,
    )
    return [_to_response(bookmark, opportunity) for bookmark, opportunity in rows]


@router.post("", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    payload: BookmarkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        bookmark, opportunity = create_or_update_bookmark(
            db=db,
            user_id=current_user.id,
            opportunity_id=payload.opportunity_id,
            notes=payload.notes,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_response(bookmark, opportunity)


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_user_bookmark(db=db, user_id=current_user.id, bookmark_id=bookmark_id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
