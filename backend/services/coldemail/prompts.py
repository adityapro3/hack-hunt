import re

from backend.scrapers.coldemail.csrankings import ProfessorCandidate


_MAX_RESEARCH_TITLE_SNIPPET = 3


def build_system_prompt() -> str:
    return (
        "You are an assistant that writes concise, professional, and genuine cold emails to professors. "
        "Always avoid spammy language, template-like phrasing, and exaggerated claims. "
        "Ground all claims about the professor's research strictly in the provided research context. "
        "Never use cliches like 'I hope this email finds you well' or generic flattery."
    )


def extract_research_titles(research_summary: str) -> list[str]:
    summary = (research_summary or "").strip()
    if not summary:
        return []

    numbered_matches = re.findall(
        r"^\s*\d+\.\s+(.+?)(?:\s+\(\d{4}\))?\s+\(semantic similarity:",
        summary,
        flags=re.MULTILINE,
    )
    titles = [_token.strip() for _token in numbered_matches if _token.strip()]
    if titles:
        return titles

    if summary.lower().startswith("recent research:"):
        parts = summary.split(":", maxsplit=1)[-1].split(";")
        return [part.strip() for part in parts if part.strip()]

    return []


def email_mentions_any_research_title(body: str, research_titles: list[str]) -> bool:
    if not body.strip() or not research_titles:
        return False
    body_l = body.casefold()
    return any(title.casefold() in body_l for title in research_titles if len(title) >= 8)


def _resolve_ask_type_guidance(ask_type: str) -> str:
    mapping = {
        "phd_inquiry": "Ask whether the professor is open to PhD applicants and what preparation they expect.",
        "research_assistant": "Ask for a research assistant opening with a practical next step.",
        "collaboration": "Ask for a small technical collaboration opportunity aligned to one paper.",
        "meeting_request": "Ask for a short meeting to discuss fit around one focused idea.",
        "internship_inquiry": "Ask for a research internship opportunity and preferred application path.",
    }
    return mapping.get(ask_type, mapping["phd_inquiry"])


def _format_student_profile_for_prompt(student_profile: dict) -> str:
    full_name = str(student_profile.get("full_name") or "").strip()
    interests = [str(item).strip() for item in student_profile.get("research_interests", []) if str(item).strip()]
    skills = [str(item).strip() for item in student_profile.get("technical_skills", []) if str(item).strip()]
    publications = [str(item).strip() for item in student_profile.get("publications", []) if str(item).strip()]
    degree = str(student_profile.get("degree") or "").strip()
    goal = str(student_profile.get("goal") or "").strip()

    project_lines: list[str] = []
    for project in student_profile.get("projects", []):
        if not isinstance(project, dict):
            continue
        title = str(project.get("title") or "").strip()
        what = str(project.get("what") or "").strip()
        impact = str(project.get("impact") or "").strip()
        if not title or not what:
            continue
        line = f"- {title}: {what}"
        if impact:
            line += f" | impact: {impact}"
        project_lines.append(line)

    lines: list[str] = []
    if full_name:
        lines.append(f"Full name: {full_name}")
    if degree:
        lines.append(f"Degree: {degree}")
    if goal:
        lines.append(f"Goal: {goal}")
    if interests:
        lines.append("Research interests: " + ", ".join(interests[:10]))
    if skills:
        lines.append("Technical skills: " + ", ".join(skills[:18]))
    if publications:
        lines.append("Student publications: " + "; ".join(publications[:5]))
    if project_lines:
        lines.append("Projects:\n" + "\n".join(project_lines[:5]))

    return "\n".join(lines) if lines else "No structured student profile details available."


def resolve_student_name(student_profile: dict) -> str | None:
    value = str(student_profile.get("full_name") or "").strip()
    return value or None


def replace_signature_placeholders(body: str, student_name: str | None) -> str:
    updated = body
    replacement = student_name or ""
    updated = re.sub(r"\[\s*your\s*name\s*\]", replacement, updated, flags=re.IGNORECASE)
    updated = re.sub(r"<\s*your\s*name\s*>", replacement, updated, flags=re.IGNORECASE)
    return updated


def build_user_prompt(
    professor: ProfessorCandidate,
    research_summary: str,
    tone: str,
    ask_type: str,
    student_profile: dict,
) -> str:
    student_profile_block = _format_student_profile_for_prompt(student_profile)
    student_name = resolve_student_name(student_profile)
    ask_type_guidance = _resolve_ask_type_guidance(ask_type)

    research_titles = extract_research_titles(research_summary)
    title_hint_block = ""
    if research_titles:
        rendered = "\n".join(
            f'- "{title}"' for title in research_titles[:_MAX_RESEARCH_TITLE_SNIPPET]
        )
        title_hint_block = (
            "Preferred paper titles to cite verbatim (choose at least one):\n"
            f"{rendered}\n\n"
        )

    signoff_rule = (
        f"8. Sign off with exactly: {student_name}.\n"
        if student_name
        else "8. Sign off using the student full name from the profile.\n"
    )

    output_format = (
        "OUTPUT FORMAT (follow exactly, no deviations):\n"
        "Line 1:   Subject: <concise subject line>\n"
        "Line 2+:  <email body - plain text, no markdown, no bullet points>\n"
        "\n"
        "Do not add any preamble, explanation, or text before 'Subject:'.\n"
        "Do not add any text after the email sign-off.\n"
    )

    context_block = (
        "--- AUTHORITATIVE CONTEXT (ground all claims here) ---\n"
        f"Professor: {professor.name}\n"
        f"University: {professor.university or 'Unknown'}\n"
        f"Country: {professor.country}\n"
        f"Ask type: {ask_type}\n"
        f"Ask guidance: {ask_type_guidance}\n"
        "\n"
        "Research Context (only source for professor's work):\n"
        f"{research_summary}\n\n"
        f"{title_hint_block}"
        "Student Profile (only source for candidate details):\n"
        f"{student_profile_block}\n"
        "--- END CONTEXT ---\n"
    )

    reasoning_nudge = (
        "Before writing, silently identify:\n"
        "- Which ONE paper to cite and why it fits the student best\n"
        "- What student skills (he knows or learnt from projects) maps most directly to that paper\n"
        "- The single most specific detail from that paper's abstract to reference\n"
        "Then write the email. Do not output this reasoning.\n"
        "\n"
    )

    hard_rules = (
        "HARD RULES (violations make the email unusable):\n"
        "1. Do NOT use placeholders like [Your Name], <skill>, or (your university).\n"
        "2. Do NOT invent publications, results, or professor research not in Research Context.\n"
        "3. Do NOT attribute student skills as professor research topics.\n"
        "4. DO NOT explain any student project, only infer what student learned from it that aligns to the professor's research.\n"
        "5. Do NOT exceed 500 words in the email body but don't be too brief, atleast 240 words should be there.\n"
        "6. DO NOT write too long paragraphs. Keep paragraphs short and concise — no more than 3-4 sentences each. \n"
        "7. Do NOT include any text outside the required output format.\n"
        f"{signoff_rule}"
    )

    soft_rules = (
        f"QUALITY RULES (tone: {tone}):\n"
        "- Open with a specific observation about the professor's work, not a self-introduction.\n"
        "- Cite at least one paper title in double quotes (in short form).\n"
        "- Include one concrete detail from that paper: a method, finding, or open problem.\n"
        "- Connect most relevant student skill or project to that paper's direction - no exaggeration.\n"
        "- Mention one or two research directions from context only, not more.\n"
        "- Write in a properly formatted email style with paragraphs, no bullet points. \n"
        "- It's not compulsory to write exactly 3 paragraphs. Make sure you follow the quality & hard rules properly. \n"
        "- End with a single, clear ask aligned to Ask Guidance. No double asks.\n"
    )

    anti_patterns = (
        "BANNED phrases (never use these or anything similar):\n"
        "- 'I came across your work'\n"
        "- 'I am deeply interested / fascinated / passionate'\n"
        "- 'Your research resonates with me'\n"
        "- 'I would love to discuss'\n"
        "- 'Please find attached'\n"
        "- Any generic opener like 'I hope this email finds you well'\n"
        "- Hollow flattery with no specific substance behind it\n"
    )

    return (
        "You are an expert at writing cold research outreach emails that get replies.\n"
        "Your emails are specific and should never sound automated.\n"
        "\n"
        f"{output_format}\n"
        f"{context_block}\n"
        f"{reasoning_nudge}"
        f"{hard_rules}\n"
        f"{soft_rules}\n"
        f"{anti_patterns}\n"
        "Now write the email:\n"
    )


def parse_email_output(raw_text: str, professor_name: str) -> tuple[str, str]:
    text = (raw_text or "").strip()
    if not text:
        return "Prospective research collaboration", f"Dear Professor {professor_name},\n\n"

    match = re.match(r"^subject\s*:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        subject = "Prospective research collaboration"
        body = text
        return subject[:200], body

    subject = match.group(1).strip()[:200]
    body = text[match.end():].strip()
    if not body:
        body = f"Dear Professor {professor_name},\n\n"
    return subject or "Prospective research collaboration", body
