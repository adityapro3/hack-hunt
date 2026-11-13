import logging

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import NewsArticle
from backend.services.admin.app_config import get_embedding_base_url
from backend.services.common.embeddings_generate import generate_embedding


logger = logging.getLogger(__name__)

def list_news_articles(
    db: Session,
    topic: str | None = None,
    q: str | None = None,
    semantic: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[NewsArticle], int]:
    stmt: Select[tuple[NewsArticle]] = select(NewsArticle)

    if topic:
        topic_value = topic.strip().lower()
        if topic_value:
            stmt = stmt.where(NewsArticle.topic == topic_value)

    if semantic and q and q.strip():
        semantic_stmt = stmt.where(NewsArticle.embedding.isnot(None))
        total_count = int(db.execute(select(func.count()).select_from(semantic_stmt.subquery())).scalar_one())
        if total_count > 0:
            try:
                query_embedding = generate_embedding(
                    q.strip(),
                    base_url=get_embedding_base_url(db),
                )
                rows = db.execute(
                    semantic_stmt
                    .order_by(NewsArticle.embedding.cosine_distance(query_embedding))
                    .limit(limit)
                    .offset(offset)
                ).scalars().all()
                return rows, total_count
            except Exception as exc:
                logger.warning("News semantic search failed; falling back to lexical search (%s)", exc)

    if q and q.strip():
        token = f"%{q.strip()}%"
        stmt = stmt.where(
            NewsArticle.title.ilike(token)
            | NewsArticle.content.ilike(token)
            | NewsArticle.source.ilike(token)
            | NewsArticle.topic.ilike(token)
        )

    total_count = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())

    rows = db.execute(
        stmt.order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return rows, total_count


def get_news_filters(db: Session) -> dict:
    topics = db.execute(
        select(distinct(NewsArticle.topic)).where(
            NewsArticle.topic.isnot(None),
            func.trim(NewsArticle.topic) != "",
            func.lower(NewsArticle.topic) != "latest",
        )
    ).scalars().all()
    return {
        "topics": sorted([item for item in topics if item]),
    }
