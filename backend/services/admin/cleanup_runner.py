from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from backend.core.opportunity_enums import OpportunityType
from backend.infra.postgres.tables import NewsArticle, Opportunity


def cleanup_expired_opportunities(
    db: Session,
) -> dict[str, int | datetime]:
    now_utc = datetime.now(timezone.utc)

    filters = [
        Opportunity.opportunity_type == OpportunityType.Hackathon,
        Opportunity.deadline.is_not(None),
        Opportunity.deadline < now_utc,
    ]

    matched_stmt = select(func.count()).select_from(Opportunity).where(*filters)
    matched = int(db.execute(matched_stmt).scalar_one())

    if matched == 0:
        return {
            "matched": matched,
            "deleted": 0,
            "now_utc": now_utc,
        }

    delete_stmt = delete(Opportunity).where(*filters)
    result = db.execute(delete_stmt)
    db.commit()

    deleted = result.rowcount if result.rowcount is not None else matched
    return {
        "matched": matched,
        "deleted": int(deleted),
        "now_utc": now_utc,
    }


def _build_outdated_news_filter(keep_days: int = 3):
    keep_days = max(1, keep_days)
    today = datetime.now(timezone.utc).date()
    include_from = today - timedelta(days=keep_days - 1)
    include_from_dt = datetime.combine(include_from, datetime.min.time(), tzinfo=timezone.utc)

    return or_(
        NewsArticle.published_at < include_from_dt,
        and_(NewsArticle.published_at.is_(None), NewsArticle.scraped_at < include_from_dt),
    )


def count_outdated_news(db: Session, keep_days: int = 3) -> int:
    outdated_filter = _build_outdated_news_filter(keep_days=keep_days)
    return int(db.execute(select(func.count()).select_from(NewsArticle).where(outdated_filter)).scalar_one())


def cleanup_outdated_news(db: Session, keep_days: int = 3) -> int:
    outdated_filter = _build_outdated_news_filter(keep_days=keep_days)

    deleted_count = int(
        db.execute(
            delete(NewsArticle).where(
                outdated_filter
            )
        ).rowcount
        or 0
    )
    db.commit()
    return deleted_count


def run_expired_cleanup(
    db: Session,
    news_keep_days: int = 3,
) -> dict:
    opportunity_result = cleanup_expired_opportunities(
        db=db,
    )

    news_keep_days = max(1, min(30, int(news_keep_days)))
    news_matched = count_outdated_news(db=db, keep_days=news_keep_days)
    news_deleted = cleanup_outdated_news(db=db, keep_days=news_keep_days) if news_matched > 0 else 0

    matched_total = int(opportunity_result["matched"]) + int(news_matched)
    deleted_total = int(opportunity_result["deleted"]) + int(news_deleted)

    return {
        "matched": matched_total,
        "deleted": deleted_total,
        "opportunity_matched": int(opportunity_result["matched"]),
        "opportunity_deleted": int(opportunity_result["deleted"]),
        "news_matched": int(news_matched),
        "news_deleted": int(news_deleted),
        "news_keep_days": news_keep_days,
        "now_utc": opportunity_result["now_utc"],
    }