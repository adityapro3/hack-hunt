import logging
from pathlib import Path
from collections.abc import Callable
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy import Select, func, or_, select

from backend.core.config import get_settings
from backend.infra.postgres.tables import NewsArticle
from backend.services.admin.app_config import record_admin_log

logger = logging.getLogger(__name__)
_MAX_TOPIC_TOKENS = 128  # saved DistilBERT was trained at this limit


_CANONICAL_LABEL_MAP = {
    "politics": "politics",
    "sports": "sports",
    "entertainment": "entertainment",
    "finance": "business",
    "business": "business",
    "health": "health",
    "science": "science",
    "world": "world",
    "lifestyle": "lifestyle",
    "crime": "crime",
    "environment": "environment",
    "education": "education",
}


class NewsTopicClassifier:
    def __init__(self, model_dir: str, default_label: str = "general"):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as exc:
            raise RuntimeError(
                "Topic classifier dependencies are missing. Install transformers and torch."
            ) from exc

        if not model_dir:
            raise RuntimeError("Topic model directory is not configured")
        model_path = Path(model_dir).expanduser()
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[3] / model_path
        if not model_path.is_dir():
            raise RuntimeError(f"Topic model directory not found: {model_path}")

        self._torch = torch
        self._default_label = default_label.strip().lower() or "general"
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        self._model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
        self._id2label = {
            int(index): str(label).strip().upper()
            for index, label in self._model.config.id2label.items()
        }
        expected_labels = {
            "POLITICS", "SPORTS", "ENTERTAINMENT", "FINANCE", "HEALTH",
            "SCIENCE", "WORLD", "LIFESTYLE", "CRIME", "ENVIRONMENT", "EDUCATION",
        }
        if (
            self._model.config.num_labels != 11
            or set(self._id2label) != set(range(11))
            or set(self._id2label.values()) != expected_labels
        ):
            raise RuntimeError("Topic model must contain the expected 11 news labels")

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model.to(self._device)
        self._model.eval()

    def _normalize_topic(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            return self._default_label
        return _CANONICAL_LABEL_MAP.get(normalized, normalized)

    def predict_category(self, text: str) -> str:
        payload = (text or "").strip()
        if not payload:
            return self._default_label

        inputs = self._tokenizer(
            payload,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=_MAX_TOPIC_TOKENS,
        )
        inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with self._torch.no_grad():
            outputs = self._model(**inputs)

        predicted_index = int(self._torch.argmax(outputs.logits, dim=-1).item())
        raw_label = self._id2label[predicted_index]
        return self._normalize_topic(raw_label)


@lru_cache(maxsize=1)
def get_topic_classifier() -> NewsTopicClassifier | None:
    settings = get_settings()

    model_dir = (settings.news_topic_model_dir or "").strip()
    if not model_dir:
        logger.warning("NEWS_TOPIC_MODEL_DIR is not set; topic classification is disabled")
        return None

    try:
        return NewsTopicClassifier(model_dir=model_dir, default_label=settings.news_topic_default_label)
    except Exception as exc:
        logger.exception("Failed to initialize topic classifier from %s", model_dir, exc_info=exc)
        return None


def classify_news_topic(text: str) -> str | None:
    classifier = get_topic_classifier()
    if classifier is None:
        return None

    try:
        return classifier.predict_category(text)
    except Exception as exc:
        logger.warning("Topic classification failed: %s", exc)
        return None


def _needs_topic_filter() -> object:
    return or_(
        NewsArticle.topic.is_(None),
        func.trim(NewsArticle.topic) == "",
        func.lower(NewsArticle.topic) == "latest",
    )


def _build_input_text(item: NewsArticle) -> str:
    # Match training order: headline first, then the article lead. The tokenizer
    # keeps the first 128 subword tokens, including special tokens.
    title = (item.title or "").strip()
    content = (item.content or "").strip()
    return f"{title} {content}".strip()



def run_news_topic_backfill(
    db: Session,
    batch_size: int = 50,
    source: str | None = None,
    run_until_empty: bool = False,
    overwrite_existing: bool = False,
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
        f"Starting news topic backfill (batch_size={batch_size}, source={source or 'all'}, run_until_empty={run_until_empty}, overwrite_existing={overwrite_existing})"
    )

    while True:
        stmt: Select[tuple[NewsArticle]] = select(NewsArticle)
        if source:
            stmt = stmt.where(NewsArticle.source == source)
        if not overwrite_existing:
            stmt = stmt.where(_needs_topic_filter())

        rows = db.execute(stmt.order_by(NewsArticle.created_at.asc()).limit(batch_size)).scalars().all()
        if not rows:
            remaining_stmt = select(func.count()).select_from(NewsArticle)
            if source:
                remaining_stmt = remaining_stmt.where(NewsArticle.source == source)
            if not overwrite_existing:
                remaining_stmt = remaining_stmt.where(_needs_topic_filter())
            remaining = int(db.execute(remaining_stmt).scalar_one())
            log(f"No more rows matched. Remaining needing topics: {remaining}")
            break

        batches_ran += 1
        processed_this_batch = 0
        log(f"Batch {batches_ran}: loaded {len(rows)} row(s) for topic classification")

        for row in rows:
            topic = classify_news_topic(_build_input_text(row))
            if not topic:
                failed += 1
                continue
            row.topic = topic
            processed += 1
            processed_this_batch += 1

        db.commit()

        remaining_stmt = select(func.count()).select_from(NewsArticle)
        if source:
            remaining_stmt = remaining_stmt.where(NewsArticle.source == source)
        if not overwrite_existing:
            remaining_stmt = remaining_stmt.where(_needs_topic_filter())
        remaining = int(db.execute(remaining_stmt).scalar_one())
        log(f"Batch {batches_ran}: processed {processed_this_batch} row(s), failed {failed}, remaining {remaining}")

        if not run_until_empty or remaining == 0 or processed_this_batch == 0:
            break

    log(f"Completed news topic backfill: processed {processed}, failed {failed}, remaining {remaining}, batches={batches_ran}")

    return {
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "batches_ran": batches_ran,
        "source": source,
        "logs": logs,
    }
