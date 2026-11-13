import base64
import binascii
import logging
import re
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from backend.infra.postgres.tables import UserColdEmailProfile
from backend.core.config import get_settings
from backend.schemas.coldemail import ColdEmailStudentProfileData
from backend.services.common.llm import LLMProvider
from backend.services.common.domain_errors import DomainValidationError
from backend.services.users.settings import get_or_create_settings


_PROFILE_PROVIDER = "oppora_free"
logger = logging.getLogger(__name__)


class _ExtractionStudentProfileData(BaseModel):
    # Keep extraction schema permissive for provider compatibility, then normalize to strict app schema.
    full_name: str | None = None
    research_interests: list[str] | None = None
    technical_skills: list[str] | None = None
    projects: list[dict] | None = None
    publications: list[str] | None = None
    goal: str | None = None
    degree: str | None = None


def parse_resume_content(filename: str, content_base64: str) -> str:
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DomainValidationError('Invalid base64 resume content') from exc

    ext = Path(filename).suffix.lower()
    if ext == '.pdf':
        try:
            import fitz

            with fitz.open(stream=raw, filetype='pdf') as doc:
                text = '\n'.join((page.get_text('text') or '') for page in doc)
        except ModuleNotFoundError as exc:
            raise DomainValidationError('PDF parsing requires PyMuPDF. Install with: python -m pip install pymupdf') from exc
        except Exception as exc:
            raise DomainValidationError('Unable to parse PDF resume') from exc
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1', errors='ignore')

    cleaned = re.sub(r'\s+', ' ', text).strip()
    if len(cleaned) < 20:
        raise DomainValidationError('Resume text appears empty or too short')

    return cleaned[:25_000]


def extract_skills_from_resume(
    db: Session,
    user_id: UUID,
    resume_text: str,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
) -> dict[str, str]:
    cleaned_resume = (resume_text or '').strip()
    if len(cleaned_resume) < 20:
        raise DomainValidationError('Resume text must be at least 20 characters')

    user_settings = get_or_create_settings(db, user_id)
    provider = LLMProvider(
        user_settings,
        preferred_provider=preferred_provider,
        preferred_model=preferred_model,
    )

    system_prompt = (
        'You extract only concrete technical skills from resumes. '
        'Return one comma-separated line with no extra explanation.'
    )
    user_prompt = (
        'Extract key technical skills from this resume. Include programming languages, libraries, frameworks, '
        'ML/AI tooling, data platforms, and core engineering technologies. Avoid soft skills.\n\n'
        f'Resume:\n{cleaned_resume[:16_000]}'
    )

    result = provider.generate(user_prompt=user_prompt, system_prompt=system_prompt)
    raw = (result.text or '').replace('\n', ',').strip()
    if not raw:
        raise DomainValidationError('Could not extract skills from resume text')

    tokens = [item.strip(' .') for item in re.split(r'[,;|]', raw) if item.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(token)

    skills_text = ', '.join(deduped[:25])
    if not skills_text:
        raise DomainValidationError('Could not extract skills from resume text')

    return {
        'skills_text': skills_text,
        'provider': result.provider,
        'model': result.model,
    }


def _normalize_profile_payload(payload: dict) -> dict:
    def _as_string_list(value: object, *, max_items: int = 20) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if not token:
                continue
            key = token.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(token)
            if len(cleaned) >= max_items:
                break
        return cleaned

    projects: list[dict] = []
    if isinstance(payload.get("projects"), list):
        for item in payload["projects"]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or "").strip()
            what = str(item.get("what") or item.get("description") or "").strip()
            impact = str(item.get("impact") or item.get("result") or "").strip() or None
            if not impact and isinstance(item.get("tech_stack"), list):
                tech_stack = [str(value).strip() for value in item.get("tech_stack") or [] if str(value).strip()]
                if tech_stack:
                    impact = f"Tech stack: {', '.join(tech_stack[:8])}"
            if not title or not what:
                continue
            projects.append(
                {
                    "title": title[:200],
                    "what": what[:500],
                    "impact": impact[:300] if impact else None,
                }
            )
            if len(projects) >= 8:
                break

    normalized = {
        "full_name": str(payload.get("full_name") or payload.get("name") or "").strip()[:120] or None,
        "research_interests": _as_string_list(payload.get("research_interests"), max_items=20),
        "technical_skills": _as_string_list(payload.get("technical_skills"), max_items=30),
        "projects": projects,
        "publications": _as_string_list(payload.get("publications"), max_items=10),
        "goal": str(payload.get("goal") or "").strip()[:300] or None,
        "degree": str(payload.get("degree") or "").strip()[:120] or None,
    }

    # Validate structure against shared schema contract.
    return ColdEmailStudentProfileData(**normalized).model_dump()


def _resolve_openai_compatible_base_url(base_url: str | None) -> str:
    value = (base_url or "").strip().rstrip("/")
    if not value:
        return "https://ollama.com/v1"

    # Ollama Cloud OpenAI-compatible endpoint uses ollama.com (not api.ollama.com).
    value = re.sub(r"^https?://api\.ollama\.com(?=/|$)", "https://ollama.com", value, flags=re.IGNORECASE)

    if value.lower().endswith("/v1"):
        return value
    return f"{value}/v1"


def _extract_student_profile_from_resume(
    resume_text: str,
) -> tuple[dict, str, str]:
    settings = get_settings()
    api_key = (settings.coldemail_profile_api_key or "").strip()
    profile_base_url = _resolve_openai_compatible_base_url(settings.coldemail_profile_base_url)
    if not api_key:
        raise DomainValidationError(
            "Platform cold-email profile API key is missing. Set COLDEMAIL_PROFILE_API_KEY in backend environment."
        )

    client = instructor.from_openai(
        OpenAI(
            api_key=api_key,
            base_url=profile_base_url,
        ),
        mode=instructor.Mode.JSON,
    )

    try:
        extracted = client.chat.completions.create(
            model=settings.coldemail_profile_model,
            temperature=0,
            response_model=_ExtractionStudentProfileData,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract structured student profiles from resumes. "
                        "Return only factual information that appears in the resume. "
                        "Output valid JSON only with keys: "
                        "full_name, research_interests, technical_skills, projects, publications, goal, degree. "
                        "For list fields, always return [] instead of null."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Extract a concise profile from this resume. "
                        "Keep lists deduplicated and compact, and set unknown fields to null.\n\n"
                        f"Resume:\n{resume_text[:10_000]}"
                    ),
                },
            ],
            max_retries=1,
        )
    except Exception as exc:
        logger.exception("Cold-email profile extraction failed")
        raise DomainValidationError(f"Structured profile extraction failed: {exc}") from exc

    normalized_profile = _normalize_profile_payload(extracted.model_dump())
    return normalized_profile, _PROFILE_PROVIDER, settings.coldemail_profile_model


def upsert_user_coldemail_profile(
    db: Session,
    user_id: UUID,
    filename: str,
    content_base64: str,
    allow_reupload: bool = False,
) -> UserColdEmailProfile:
    resume_text = parse_resume_content(filename=filename, content_base64=content_base64)
    row = db.query(UserColdEmailProfile).filter(UserColdEmailProfile.user_id == user_id).one_or_none()
    if row is not None and not allow_reupload:
        raise DomainValidationError(
            "Profile already exists. Set allow_reupload=true to replace the saved profile."
        )

    profile_json, provider_name, model_name = _extract_student_profile_from_resume(
        resume_text=resume_text,
    )

    if row is None:
        row = UserColdEmailProfile(
            user_id=user_id,
            resume_filename=filename,
            resume_text=resume_text,
            profile_json=profile_json,
            profile_provider=provider_name,
            profile_model=model_name,
        )
        db.add(row)
    else:
        row.resume_filename = filename
        row.resume_text = resume_text
        row.profile_json = profile_json
        row.profile_provider = provider_name
        row.profile_model = model_name

    db.commit()
    db.refresh(row)
    return row


def get_user_coldemail_profile(
    db: Session,
    user_id: UUID,
) -> UserColdEmailProfile | None:
    return db.query(UserColdEmailProfile).filter(UserColdEmailProfile.user_id == user_id).one_or_none()
