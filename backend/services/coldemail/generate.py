import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.infra.postgres.tables import ColdEmailDraft, UserColdEmailProfile
from backend.schemas import ColdEmailGenerateRequest
from backend.services.common.llm import LLMProvider, OllamaBackend
from backend.services.common.ai_errors import LLMProviderError
from backend.services.common.domain_errors import DomainValidationError
from backend.services.coldemail.drafts import serialize_draft
from backend.services.coldemail.professors import (
    record_professor_seen, 
    resolve_professor_candidates_for_generation,
)
from backend.services.coldemail.prompts import (
    build_system_prompt,
    build_user_prompt,
    email_mentions_any_research_title,
    extract_research_titles,
    parse_email_output,
    replace_signature_placeholders,
    resolve_student_name,
)
from backend.services.coldemail.research import build_user_research_query, fetch_research_summary
from backend.services.users.settings import get_or_create_settings


logger = logging.getLogger(__name__)

_FREE_TIER_MAX_COLD_EMAILS = 5
_FREE_TIER_PROVIDER = "oppora_free"
_FREE_TIER_MODEL = "gemma4:31b-cloud"


def _normalize_countries(countries: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in countries:
        country = item.strip()
        if not country:
            continue
        key = country.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(country)
    return cleaned


def _count_user_drafts_today(db: Session, user_id: UUID) -> int:
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.execute(
            select(func.count())
            .select_from(ColdEmailDraft)
            .where(
                ColdEmailDraft.user_id == user_id,
                ColdEmailDraft.created_at >= start_of_day,
            )
        ).scalar_one()
    )


async def generate_cold_email_event_stream(
    db: Session,
    user_id: UUID,
    payload: ColdEmailGenerateRequest,
):
    app_settings = get_settings()
    countries = _normalize_countries(payload.countries)
    if not countries:
        raise DomainValidationError("At least one country is required")

    if payload.max_professors > app_settings.coldemail_max_professors_per_run:
        raise DomainValidationError(
            f"max_professors must be <= {app_settings.coldemail_max_professors_per_run} per country"
        )

    existing_today = _count_user_drafts_today(db=db, user_id=user_id)
    if existing_today >= app_settings.coldemail_rate_limit_per_day:
        raise DomainValidationError("Daily cold-email limit reached")

    user_settings = get_or_create_settings(db, user_id)
    user_profile = db.execute(
        select(UserColdEmailProfile).where(UserColdEmailProfile.user_id == user_id)
    ).scalar_one_or_none()
    if user_profile is None:
        raise DomainValidationError(
            "Resume profile not found. Upload resume in Cold Email profile setup before generating drafts."
        )

    free_tier_remaining: int | None = None
    if payload.use_free_tier:
        already_used = int(user_settings.free_scribe_used or 0)
        free_tier_remaining = _FREE_TIER_MAX_COLD_EMAILS - already_used
        if free_tier_remaining <= 0:
            raise DomainValidationError("Free-tier cold-email limit reached (5/5 used)")

        api_key = (app_settings.coldemail_profile_api_key or "").strip()
        if not api_key:
            raise DomainValidationError(
                "Free-tier cold-email is not configured. Set COLDEMAIL_PROFILE_API_KEY."
            )

        provider = OllamaBackend(
            model=_FREE_TIER_MODEL,
            base_url="https://api.ollama.com",
            provider_name=_FREE_TIER_PROVIDER,
            api_key=api_key,
            localhost_retry=False,
        )
        provider_name = provider.provider
        model_name = provider.model
    else:
        provider = LLMProvider(
            user_settings,
            preferred_provider=payload.provider,
            preferred_model=payload.model,
        )
        provider_name = provider.provider_name
        model_name = provider.model_name

    yield {
        "type": "meta",
        "provider": provider_name,
        "model": model_name,
        "countries": countries,
        "max_professors": payload.max_professors,
        "ask_type": payload.ask_type,
        "use_free_tier": payload.use_free_tier,
        "free_tier_remaining": free_tier_remaining,
    }

    yield {
        "type": "progress",
        "stage": "catalog",
        "message": "Loading professor catalogue for: " + ", ".join(countries),
    }

    candidates, diagnostics = await resolve_professor_candidates_for_generation(
        db=db,
        user_id=user_id,
        website=payload.website,
        countries=countries,
        max_professors_per_country=payload.max_professors,
    )

    if diagnostics.unsupported_countries:
        yield {
            "type": "progress",
            "stage": "catalog",
            "message": (
                "Skipped unsupported country names: "
                + ", ".join(diagnostics.unsupported_countries)
            ),
        }

    if diagnostics.page_load_failures:
        failed_countries = ", ".join(sorted(diagnostics.page_load_failures.keys()))
        yield {
            "type": "progress",
            "stage": "catalog",
            "message": f"Failed to load ranking pages for: {failed_countries}",
        }

    if diagnostics.countries_with_no_candidates:
        yield {
            "type": "progress",
            "stage": "catalog",
            "message": (
                "No faculty entries found for: "
                + ", ".join(diagnostics.countries_with_no_candidates)
            ),
        }

    if not candidates:
        logger.info("Cold-email run completed with zero candidates for countries=%s", countries)
        yield {
            "type": "progress",
            "stage": "done",
            "message": "No professors matched the current catalogue filters. Try different countries.",
        }
        yield {
            "type": "done",
            "generated_count": 0,
            "failed_count": 0,
        }
        return

    generated_count = 0
    failed_count = 0
    user_query = build_user_research_query(
        student_profile=user_profile.profile_json or {},
        resume_text=user_profile.resume_text,
    )

    for candidate in candidates:
        if payload.use_free_tier and free_tier_remaining is not None and free_tier_remaining <= 0:
            yield {
                "type": "progress",
                "stage": "done",
                "message": "Free-tier outreach drafts limit reached for this account (5 total).",
            }
            break

        yield {
            "type": "progress",
            "stage": "research",
            "message": f"Extracting research context for {candidate.name}",
            "country": candidate.country,
            "professor_name": candidate.name,
        }

        research_summary = await fetch_research_summary(
            db=db,
            profile_url=candidate.profile_url,
            user_query=user_query,
            professor_name=candidate.name,
            university_name=candidate.university,
            country=candidate.country,
        )
        user_prompt = build_user_prompt(
            professor=candidate,
            research_summary=research_summary,
            tone=payload.tone,
            ask_type=payload.ask_type,
            student_profile=user_profile.profile_json or {},
        )

        try:
            llm_result = await asyncio.to_thread(
                provider.generate,
                user_prompt,
                build_system_prompt(),
            )
        except LLMProviderError as exc:
            failed_count += 1
            yield {
                "type": "progress",
                "stage": "error",
                "message": f"Generation failed for {candidate.name}: {exc}",
                "country": candidate.country,
                "professor_name": candidate.name,
            }
            continue

        research_titles = extract_research_titles(research_summary)
        if research_titles and not email_mentions_any_research_title(llm_result.text, research_titles):
            retry_prompt = (
                user_prompt
                + "\n\nRewrite the email. The previous draft was too generic. "
                + "You must cite at least one paper title (in short) from the provided list in double quotes and tie it "
                + "to one concrete detail from its abstract."
            )
            try:
                llm_result = await asyncio.to_thread(
                    provider.generate,
                    retry_prompt,
                    build_system_prompt(),
                )
            except LLMProviderError:
                pass

        student_name = resolve_student_name(user_profile.profile_json or {})
        subject, body = parse_email_output(llm_result.text, candidate.name)
        body = replace_signature_placeholders(body, student_name)
        row = ColdEmailDraft(
            user_id=user_id,
            country=candidate.country,
            source="csrankings",
            professor_name=candidate.name,
            university_name=candidate.university,
            profile_url=candidate.profile_url,
            research_summary=research_summary,
            subject_line=subject,
            body=body,
            tone=payload.tone,
            ask_type=payload.ask_type,
            provider=llm_result.provider,
            model=llm_result.model,
            status="draft",
        )
        db.add(row)
        record_professor_seen(db=db, user_id=user_id, candidate=candidate)
        if payload.use_free_tier:
            user_settings.free_scribe_used = int(user_settings.free_scribe_used or 0) + 1
        db.commit()
        db.refresh(row)

        generated_count += 1
        if payload.use_free_tier and free_tier_remaining is not None:
            free_tier_remaining = max(0, free_tier_remaining - 1)
        yield {
            "type": "draft",
            "draft": serialize_draft(row).model_dump(mode="json"),
        }

    yield {
        "type": "done",
        "generated_count": generated_count,
        "failed_count": failed_count,
    }
