import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.infra.postgres.tables import ColdEmailDraft
from backend.services.common.domain_errors import DomainNotFoundError, DomainValidationError


_VALID_STATUSES = {"draft", "approved", "sent", "failed"}
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_recipient(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or not _EMAIL_PATTERN.match(normalized):
        raise DomainValidationError("recipient_email must be a valid email address")
    return normalized


def _get_draft_for_user_or_raise(db: Session, user_id: UUID, draft_id: UUID) -> ColdEmailDraft:
    row = db.execute(
        select(ColdEmailDraft).where(
            ColdEmailDraft.id == draft_id,
            ColdEmailDraft.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise DomainNotFoundError("Cold email draft not found")
    return row


def approve_cold_email_draft(
    db: Session,
    user_id: UUID,
    draft_id: UUID,
    recipient_email: str,
) -> ColdEmailDraft:
    row = _get_draft_for_user_or_raise(db=db, user_id=user_id, draft_id=draft_id)
    if row.status not in _VALID_STATUSES:
        row.status = "draft"

    row.recipient_email = _validate_recipient(recipient_email)
    row.status = "approved"
    row.approved_at = datetime.now(timezone.utc)
    row.last_error = None

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _build_message(row: ColdEmailDraft, recipient_email: str) -> EmailMessage:
    settings = get_settings()
    sender = (settings.smtp_from_email or settings.smtp_username or "").strip()
    if not sender:
        raise DomainValidationError("SMTP sender is not configured. Set SMTP_FROM_EMAIL or SMTP_USERNAME.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient_email
    message["Subject"] = row.subject_line
    message.set_content(row.body)
    return message


def _send_with_smtp(message: EmailMessage) -> None:
    settings = get_settings()
    host = (settings.smtp_host or "").strip()
    username = (settings.smtp_username or "").strip() or None
    password = settings.smtp_password

    if not host:
        raise DomainValidationError("SMTP host is not configured. Set SMTP_HOST.")

    with smtplib.SMTP(host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if username:
            if not password:
                raise DomainValidationError("SMTP password is required when SMTP username is configured.")
            server.login(username, password)
        server.send_message(message)


def send_cold_email_draft(
    db: Session,
    user_id: UUID,
    draft_id: UUID,
    recipient_email: str | None = None,
) -> ColdEmailDraft:
    row = _get_draft_for_user_or_raise(db=db, user_id=user_id, draft_id=draft_id)

    resolved_recipient = _validate_recipient(recipient_email or row.recipient_email or "")
    row.recipient_email = resolved_recipient

    if row.status == "sent":
        raise DomainValidationError("Draft already sent")

    if row.status == "draft":
        row.status = "approved"
        row.approved_at = row.approved_at or datetime.now(timezone.utc)

    try:
        message = _build_message(row=row, recipient_email=resolved_recipient)
        _send_with_smtp(message)
    except Exception as exc:
        row.status = "failed"
        row.last_error = str(exc)
        db.add(row)
        db.commit()
        db.refresh(row)
        raise DomainValidationError(f"Failed to send email: {exc}") from exc

    row.status = "sent"
    row.sent_at = datetime.now(timezone.utc)
    row.last_error = None

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_cold_email_draft(
    db: Session,
    user_id: UUID,
    draft_id: UUID,
) -> None:
    row = _get_draft_for_user_or_raise(db=db, user_id=user_id, draft_id=draft_id)
    db.delete(row)
    db.commit()
