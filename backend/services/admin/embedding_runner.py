import logging
from collections.abc import Callable
from typing import Type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import NewsArticle, Opportunity
from backend.services.common.embeddings_generate import (
    generate_embedding,
    generate_embeddings,
)
from backend.services.admin.app_config import record_admin_log

logger = logging.getLogger(__name__)


def build_opportunity_embedding_text(item: Opportunity) -> str:
    return (
        f"{item.title}. {item.opportunity_type or 'Hackathon'}. "
        f"Source: {item.source}. "
        f"Domains: {', '.join(item.domains or [])}. "
        f"Mode: {item.mode or 'online'}. "
        f"Deadline: {item.deadline or 'unknown'}. "
        f"Prize: {item.prize_money or 'unknown'}. "
        f"Location: {item.location or 'unknown'}. "
        f"{item.description or ''}"
    )


def build_news_embedding_text(item: NewsArticle) -> str:
    return (
        f"{item.title or ''}. "
        f"Source: {item.source or 'unknown'}. "
        f"Topic: {item.topic or 'latest'}. "
        f"Published: {item.published_at or 'unknown'}. "
        f"{item.content or ''}. "
    )


def run_embedding_backfill(
    db: Session,
    model_class: Type[Opportunity | NewsArticle],
    batch_size: int = 50,
    source: str | None = None,
    run_until_empty: bool = False,
    embedding_base_url: str | None = None,
    emit_log: Callable[[str], None] | None = None,
) -> dict[str, int | str | list[str] | None]:
    processed = 0
    failed = 0
    batches_ran = 0
    remaining = 0
    logs: list[str] = []

    def log(message: str) -> None:
        record_admin_log(logs, message, emit_log)

    log(
        f"Starting {model_class.__name__} embedding backfill (batch_size={batch_size}, source={source or 'all'}, run_until_empty={run_until_empty})"
    )

    while True:
        stmt = select(model_class).where(model_class.embedding.is_(None))
        if source:
            stmt = stmt.where(model_class.source == source)

        rows = db.execute(stmt.order_by(model_class.created_at.asc()).limit(batch_size)).scalars().all()
        if not rows:
            remaining_stmt = select(func.count()).select_from(model_class).where(model_class.embedding.is_(None))
            if source:
                remaining_stmt = remaining_stmt.where(model_class.source == source)
            remaining = int(db.execute(remaining_stmt).scalar_one())
            break

        batches_ran += 1
        log(f"Batch {batches_ran}: loaded {len(rows)} row(s) needing embeddings")

        if model_class == Opportunity:
            log(f"Processing batch {batches_ran} for Opportunities embeddings (source={source or 'all'})")
            texts = [build_opportunity_embedding_text(row) for row in rows]
        elif model_class == NewsArticle:
            log(f"Processing batch {batches_ran} for News Articles embeddings (source={source or 'all'})")
            texts = [build_news_embedding_text(row) for row in rows]
        else:
            texts = []

        vectors: list[list[float]] | None = None
        processed_this_batch = 0

        try:
            vectors = generate_embeddings(texts, base_url=embedding_base_url)
            if len(vectors) != len(rows):
                raise RuntimeError(f"Expected {len(rows)} vectors but got {len(vectors)}")
            log(f"Batch {batches_ran}: generated embeddings for {len(rows)} row(s)")
        except Exception as exc:
            logger.warning(
                "%s embedding batch failed; falling back to per-row generation (%s)",
                model_class.__name__,
                exc,
            )
            log(f"Batch {batches_ran}: bulk embedding failed, falling back to per-row generation ({exc})")

        if vectors is not None:
            for row, vector in zip(rows, vectors):
                row.embedding = vector
                processed += 1
                processed_this_batch += 1
        else:
            for row, text in zip(rows, texts):
                try:
                    row.embedding = generate_embedding(text, base_url=embedding_base_url)
                    processed += 1
                    processed_this_batch += 1
                except Exception as exc:
                    failed += 1
                    logger.warning(
                        "Embedding backfill failed for %s %s (%s)",
                        model_class.__name__,
                        row.id,
                        exc,
                    )
                    log(f"Batch {batches_ran}: failed for row {row.id} ({exc})")

        db.commit()

        remaining_stmt = select(func.count()).select_from(model_class).where(model_class.embedding.is_(None))
        if source:
            remaining_stmt = remaining_stmt.where(model_class.source == source)

        remaining = int(db.execute(remaining_stmt).scalar_one())
        log(f"Batch {batches_ran}: processed {processed_this_batch} row(s), remaining {remaining}")

        if not run_until_empty or remaining == 0 or processed_this_batch == 0:
            break

    log(
        f"Completed {model_class.__name__} embedding backfill: processed {processed}, failed {failed}, remaining {remaining}, batches={batches_ran}"
    )

    return {
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "batches_ran": batches_ran,
        "source": source,
        "logs": logs,
    }
