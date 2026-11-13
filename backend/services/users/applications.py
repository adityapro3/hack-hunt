from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from backend.core.opportunity_enums import OpportunityType, parse_opportunity_type
from backend.infra.postgres.tables import Application, Opportunity
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError

VALID_APPLICATION_STATUSES = {"interested", "applied", "in_progress", "accepted", "rejected"}


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


def validate_application_status(raw_status: str) -> str:
    status_value = raw_status.strip().lower()
    if status_value not in VALID_APPLICATION_STATUSES:
        raise DomainValidationError(f"Invalid status: {raw_status}")
    return status_value


def list_user_applications(
    db: Session,
    user_id: UUID,
    opportunity_type: str | None = None,
    status_filter: str | None = None,
) -> list[tuple[Application, Opportunity]]:
    stmt: Select = select(Application, Opportunity).join(
        Opportunity, Opportunity.id == Application.opportunity_id
    )
    stmt = stmt.where(
        Application.user_id == user_id,
        Opportunity.opportunity_type == OpportunityType.Hackathon,
    )

    if opportunity_type:
        parsed_type = parse_opportunity_type(opportunity_type)
        if parsed_type != OpportunityType.Hackathon:
            return []
        stmt = stmt.where(Opportunity.opportunity_type == parsed_type)
    if status_filter:
        stmt = stmt.where(Application.status == validate_application_status(status_filter))

    stmt = stmt.order_by(Application.updated_at.desc())
    return db.execute(stmt).all()


def create_or_update_application(
    db: Session,
    user_id: UUID,
    opportunity_id: UUID,
    status: str,
    applied_at,
    notes: str | None,
) -> tuple[Application, Opportunity]:
    opportunity = _get_hackathon_opportunity_or_raise(db=db, opportunity_id=opportunity_id)

    normalized_status = validate_application_status(status)

    existing = db.execute(
        select(Application).where(
            Application.user_id == user_id,
            Application.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.status = normalized_status
        existing.applied_at = applied_at
        existing.notes = notes
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing, opportunity

    application = Application(
        user_id=user_id,
        opportunity_id=opportunity_id,
        status=normalized_status,
        applied_at=applied_at,
        notes=notes,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application, opportunity


def update_user_application(
    db: Session,
    user_id: UUID,
    application_id: UUID,
    status: str | None,
    applied_at,
    notes: str | None,
) -> tuple[Application, Opportunity]:
    application = db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not application:
        raise DomainNotFoundError("Application not found")

    if status is not None:
        application.status = validate_application_status(status)
    if applied_at is not None:
        application.applied_at = applied_at
    if notes is not None:
        application.notes = notes

    db.add(application)
    db.commit()
    db.refresh(application)

    opportunity = _get_hackathon_opportunity_or_raise(db=db, opportunity_id=application.opportunity_id)

    return application, opportunity


def delete_user_application(db: Session, user_id: UUID, application_id: UUID) -> None:
    result = db.execute(
        delete(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise DomainNotFoundError("Application not found")
    db.commit()
