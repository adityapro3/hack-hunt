from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import Opportunity
from backend.services.common.domain_errors import DomainNotFoundError
from backend.core.opportunity_enums import (
    OpportunityType, 
    parse_opportunity_status, 
    parse_opportunity_type,
)


def enum_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, PyEnum):
        return str(value.value)
    return str(value)


def list_opportunities(
    db: Session,
    opportunity_type: str | None = None,
    mode: str | None = None,
    domain: str | None = None,
    skill: str | None = None,
    status: str | None = None,
    source: str | None = None,
    sort: str = "deadline",
    limit: int = 50,
    offset: int = 0,
) -> list[Opportunity]:
    stmt: Select[tuple[Opportunity]] = select(Opportunity).where(
        Opportunity.opportunity_type == OpportunityType.Hackathon
    )

    if opportunity_type:
        parsed_type = parse_opportunity_type(opportunity_type)
        if parsed_type != OpportunityType.Hackathon:
            return []
        stmt = stmt.where(Opportunity.opportunity_type == parsed_type)
    if mode:
        stmt = stmt.where(Opportunity.mode == mode)
    if domain:
        stmt = stmt.where(Opportunity.domains.any(domain))
    if skill:
        stmt = stmt.where(Opportunity.skills.any(skill))
    if status:
        stmt = stmt.where(Opportunity.status == parse_opportunity_status(status))
    if source:
        stmt = stmt.where(Opportunity.source == source)

    if sort == "created_at":
        stmt = stmt.order_by(Opportunity.created_at.desc())
    else:
        stmt = stmt.order_by(Opportunity.deadline.asc().nullslast(), Opportunity.created_at.desc())

    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


def get_opportunity_filters(
    db: Session,
    opportunity_type: str | None = None,
) -> dict[str, list]:
    scoped_filters = [Opportunity.opportunity_type == OpportunityType.Hackathon]
    if isinstance(opportunity_type, str) and opportunity_type:
        parsed_type = parse_opportunity_type(opportunity_type)
        if parsed_type != OpportunityType.Hackathon:
            return {
                "types": [],
                "domains": [],
                "skills": [],
                "modes": [],
                "statuses": [],
                "sources": [],
            }
        scoped_filters.append(Opportunity.opportunity_type == parsed_type)

    types_stmt = select(distinct(Opportunity.opportunity_type))
    statuses_stmt = select(distinct(Opportunity.status))
    sources_stmt = select(distinct(Opportunity.source))
    modes_stmt = select(distinct(Opportunity.mode)).where(Opportunity.mode.isnot(None))
    if scoped_filters:
        types_stmt = types_stmt.where(*scoped_filters)
        statuses_stmt = statuses_stmt.where(*scoped_filters)
        sources_stmt = sources_stmt.where(*scoped_filters)
        modes_stmt = modes_stmt.where(*scoped_filters)

    types = db.execute(types_stmt).scalars().all()
    modes = db.execute(modes_stmt).scalars().all()
    statuses = db.execute(statuses_stmt).scalars().all()
    sources = db.execute(sources_stmt).scalars().all()

    domains = (
        db.execute(
            select(func.distinct(func.unnest(Opportunity.domains))).where(
                Opportunity.domains.isnot(None),
                *scoped_filters,
            )
        )
        .scalars()
        .all()
    )
    skills = (
        db.execute(
            select(func.distinct(func.unnest(Opportunity.skills))).where(
                Opportunity.skills.isnot(None),
                *scoped_filters,
            )
        )
        .scalars()
        .all()
    )

    return {
        "types": sorted([enum_value(x) for x in types if x]),
        "domains": sorted([x for x in domains if x]),
        "skills": sorted([x for x in skills if x]),
        "modes": sorted([x for x in modes if x]),
        "statuses": sorted([enum_value(x) for x in statuses if x]),
        "sources": sorted([x for x in sources if x]),
    }


def get_opportunity_or_raise(db: Session, opportunity_id: UUID) -> Opportunity:
    obj = db.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.opportunity_type == OpportunityType.Hackathon,
        )
    ).scalar_one_or_none()
    if not obj:
        raise DomainNotFoundError("Opportunity not found")
    return obj
