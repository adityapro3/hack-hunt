from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from backend.core.opportunity_enums import OpportunityType
from backend.core.opportunity_enums import parse_opportunity_type
from backend.infra.postgres.tables import Bookmark, Opportunity
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError


def _get_hackathon_opportunity_or_raise(db: Session, opportunity_id: UUID) -> Opportunity:
    opportunity_exists = db.execute(
        select(Opportunity.id).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()
    if opportunity_exists is None:
        raise DomainNotFoundError("Opportunity not found")

    opportunity = db.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.opportunity_type == OpportunityType.Hackathon,
        )
    ).scalar_one_or_none()
    if not opportunity:
        raise DomainValidationError("Only hackathon opportunities are supported")
    return opportunity


def list_user_bookmarks(
    db: Session,
    user_id: UUID,
    opportunity_type: str | None = None,
) -> list[tuple[Bookmark, Opportunity]]:
    stmt: Select = (
        select(Bookmark, Opportunity)
        .join(Opportunity, Opportunity.id == Bookmark.opportunity_id)
        .where(
            Bookmark.user_id == user_id,
            Opportunity.opportunity_type == OpportunityType.Hackathon,
        )
    )
    if opportunity_type:
        parsed_type = parse_opportunity_type(opportunity_type)
        if parsed_type != OpportunityType.Hackathon:
            return []
        stmt = stmt.where(Opportunity.opportunity_type == parsed_type)
    stmt = stmt.order_by(Bookmark.created_at.desc())

    return db.execute(stmt).all()


def create_or_update_bookmark(
    db: Session,
    user_id: UUID,
    opportunity_id: UUID,
    notes: str | None,
) -> tuple[Bookmark, Opportunity]:
    opportunity = _get_hackathon_opportunity_or_raise(db=db, opportunity_id=opportunity_id)

    existing = db.execute(
        select(Bookmark).where(
            Bookmark.user_id == user_id,
            Bookmark.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.notes = notes
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing, opportunity

    bookmark = Bookmark(user_id=user_id, opportunity_id=opportunity_id, notes=notes)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark, opportunity


def delete_user_bookmark(db: Session, user_id: UUID, bookmark_id: UUID) -> None:
    result = db.execute(
        delete(Bookmark).where(
            Bookmark.id == bookmark_id,
            Bookmark.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise DomainNotFoundError("Bookmark not found")
    db.commit()
