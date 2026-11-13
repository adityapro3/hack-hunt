import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import ColdEmailDraft
from backend.schemas import ColdEmailDraftResponse


def _extract_research_matches(research_summary: str | None) -> list[dict[str, object]]:
    summary = (research_summary or "").strip()
    if not summary:
        return []

    lines = summary.splitlines()
    item_pattern = re.compile(
        r"^\s*\d+\.\s+(.+?)(?:\s+\((\d{4})\))?\s+\(semantic similarity:\s*([0-9]*\.?[0-9]+)\)\s*$"
    )
    results: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        match = item_pattern.match(line)
        if match:
            title = match.group(1).strip()
            year_text = match.group(2)
            score_text = match.group(3)
            current = {
                "title": title,
                "similarity_score": float(score_text),
                "year": int(year_text) if year_text else None,
                "url": None,
                "abstract": None,
            }
            results.append(current)
            continue

        if current is None:
            continue

        if line.lower().startswith("url:"):
            url = line.split(":", maxsplit=1)[-1].strip()
            if url:
                current["url"] = url
            continue

        if line.lower().startswith("abstract:"):
            abstract = line.split(":", maxsplit=1)[-1].strip()
            if abstract:
                current["abstract"] = abstract

    return results


def list_cold_email_drafts(
    db: Session,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ColdEmailDraft], int]:
    drafts = db.execute(
        select(ColdEmailDraft)
        .where(ColdEmailDraft.user_id == user_id)
        .order_by(ColdEmailDraft.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    total_count = int(
        db.execute(
            select(func.count()).select_from(ColdEmailDraft).where(ColdEmailDraft.user_id == user_id)
        ).scalar_one()
    )
    return drafts, total_count


def serialize_draft(row: ColdEmailDraft) -> ColdEmailDraftResponse:
    return ColdEmailDraftResponse(
        id=row.id,
        country=row.country,
        source=row.source,
        professor_name=row.professor_name,
        university_name=row.university_name,
        profile_url=row.profile_url,
        research_summary=row.research_summary,
        research_matches=_extract_research_matches(row.research_summary),
        subject_line=row.subject_line,
        body=row.body,
        recipient_email=row.recipient_email,
        tone=row.tone,
        ask_type=row.ask_type,
        provider=row.provider,
        model=row.model,
        status=row.status,
        approved_at=row.approved_at,
        sent_at=row.sent_at,
        last_error=row.last_error,
        created_at=row.created_at,
    )
