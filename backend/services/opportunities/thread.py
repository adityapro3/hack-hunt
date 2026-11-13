from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import ChatMessage, ChatThread
from backend.services.common.domain_errors import DomainNotFoundError


def thread_title_from_message(message: str) -> str:
    title = message.strip().replace("\n", " ")
    return (title[:80] or "New chat").strip()


def get_thread_for_user_or_raise(db: Session, thread_id: UUID, user_id: UUID) -> ChatThread:
    thread = db.execute(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    ).scalar_one_or_none()
    if not thread:
        raise DomainNotFoundError("Chat thread not found")
    return thread


def list_threads_for_user(db: Session, user_id: UUID, limit: int = 100) -> list[dict]:
    threads = db.execute(
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
        .limit(limit)
    ).scalars().all()

    rows: list[dict] = []
    for thread in threads:
        message_count = int(
            db.execute(
                select(func.count()).select_from(ChatMessage).where(ChatMessage.thread_id == thread.id)
            ).scalar_one()
        )
        last_message = db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.thread_id == thread.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        rows.append(
            {
                "id": thread.id,
                "title": thread.title,
                "message_count": message_count,
                "last_message_preview": last_message[:120] if last_message else None,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
            }
        )

    return rows


def create_thread_for_user(db: Session, user_id: UUID, title: str | None = None) -> ChatThread:
    clean_title = (title or "New chat").strip() or "New chat"
    thread = ChatThread(user_id=user_id, title=clean_title[:200])
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def delete_thread_for_user(db: Session, thread_id: UUID, user_id: UUID) -> None:
    thread = get_thread_for_user_or_raise(db=db, thread_id=thread_id, user_id=user_id)
    db.delete(thread)
    db.commit()


def list_messages_for_thread(db: Session, thread_id: UUID) -> list[ChatMessage]:
    return db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()


def load_recent_history(db: Session, thread_id: UUID, limit: int = 8) -> list[dict[str, str]]:
    history_rows = db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [{"role": row.role, "content": row.content} for row in reversed(history_rows)]


def get_or_create_thread_for_message(
    db: Session,
    user_id: UUID,
    thread_id: UUID | None,
    message: str,
) -> ChatThread:
    if thread_id:
        return get_thread_for_user_or_raise(db=db, thread_id=thread_id, user_id=user_id)

    thread = ChatThread(user_id=user_id, title=thread_title_from_message(message))
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def save_chat_exchange(
    db: Session,
    thread: ChatThread,
    user_message: str,
    assistant_message: str,
    provider: str,
    model: str,
    context: list[dict],
) -> None:
    user_message_row = ChatMessage(
        thread_id=thread.id,
        role="user",
        content=user_message,
    )
    assistant_message_row = ChatMessage(
        thread_id=thread.id,
        role="assistant",
        content=assistant_message,
        provider=provider,
        model=model,
        context=context,
    )

    thread.updated_at = datetime.now(timezone.utc)
    if thread.title == "New chat":
        thread.title = thread_title_from_message(user_message)

    db.add(thread)
    db.add(user_message_row)
    db.add(assistant_message_row)
    db.commit()
