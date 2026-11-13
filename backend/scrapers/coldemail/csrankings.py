import asyncio
import logging
import re
from dataclasses import dataclass

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_REGION_CODES = {
    "argentina": "ar",
    "australia": "au",
    "austria": "at",
    "bangladesh": "bd",
    "belgium": "be",
    "brazil": "br",
    "bulgaria": "bg",
    "canada": "ca",
    "chile": "cl",
    "china": "cn",
    "colombia": "co",
    "cyprus": "cy",
    "czech republic": "cz",
    "denmark": "dk",
    "egypt": "eg",
    "estonia": "ee",
    "finland": "fi",
    "france": "fr",
    "germany": "de",
    "greece": "gr",
    "hong kong": "hk",
    "hungary": "hu",
    "india": "in",
    "indonesia": "id",
    "iran": "ir",
    "ireland": "ie",
    "israel": "il",
    "italy": "it",
    "japan": "jp",
    "jordan": "jo",
    "lebanon": "lb",
    "luxembourg": "lu",
    # "macao": "mo",
    "malaysia": "my",
    "malta": "mt",
    "morocco": "ma",
    "netherlands": "nl",
    "new zealand": "nz",
    "norway": "no",
    "pakistan": "pk",
    "philippines": "ph",
    "poland": "pl",
    "portugal": "pt",
    "qatar": "qa",
    "romania": "ro",
    "russia": "ru",
    "saudi arabia": "sa",
    "singapore": "sg",
    "slovakia": "sk",
    "south africa": "za",
    "south korea": "kr",
    "spain": "es",
    "sri lanka": "lk",
    "sweden": "se",
    "switzerland": "ch",
    "thailand": "th",
    "taiwan": "tw",
    "turkey": "tr",
    "united arab emirates": "ae",
    "united kingdom": "gb",
    "vietnam": "vn",
    "usa": "us",
}


@dataclass
class ProfessorCandidate:
    country: str
    name: str
    university: str | None
    profile_url: str | None
    raw_name: str | None = None
    raw_university: str | None = None


@dataclass
class ScrapeDiagnostics:
    unsupported_countries: list[str]
    page_load_failures: dict[str, str]
    countries_with_no_candidates: list[str]


def _normalize_website(url: str) -> str:
    value = (url or "https://csrankings.org").strip()
    if not value:
        value = "https://csrankings.org"
    if not value.lower().startswith("http"):
        value = f"https://{value}"
    if not value.lower().endswith("/#/index?ai&vision&mlmining&nlp&inforet&act"):
        value = value.rstrip("/") + "/#/index?ai&vision&mlmining&nlp&inforet&act"
    return value


def _resolve_country_code(country: str) -> str | None:
    return _REGION_CODES.get(country.strip().lower())


def _clean_professor_name(raw_name: str) -> str:
    # CSRankings occasionally appends numeric artifacts (for example: "0002").
    cleaned = re.sub(r"\d+", " ", raw_name or "")
    return re.sub(r"\s+", " ", cleaned).strip(" .,-")


def get_supported_country_names() -> list[str]:
    return list(_REGION_CODES.keys())


async def _extract_candidates_from_ranking_table(
    page,
    country: str,
    limit: int,
) -> list[ProfessorCandidate]:
    payload = await page.evaluate(
        """(maxEntries) => {
            const ranking = document.querySelector('table#ranking');
            if (!ranking) {
                return { error: 'ranking table not found', candidates: [] };
            }

            const widgetSpans = Array.from(ranking.querySelectorAll("span.hovertip[id$='-widget']"));
            const candidates = [];

            for (const widget of widgetSpans) {
                if (candidates.length >= maxEntries) {
                    break;
                }

                const institutionToken = widget.id.replace(/-widget$/, '');
                const cell = widget.closest('td');
                const institutionSpans = cell
                    ? Array.from(cell.querySelectorAll("span[onclick^='csr.toggleFaculty']"))
                    : [];
                const institutionSpan = institutionSpans.length > 1
                    ? institutionSpans[institutionSpans.length - 1]
                    : (institutionSpans[0] || null);
                const rawUniversity = institutionSpan?.textContent || '';
                const university = rawUniversity.trim() || null;

                if (window.csr && typeof window.csr.toggleFaculty === 'function') {
                    window.csr.toggleFaculty(institutionToken);
                }

                const facultyDiv = document.getElementById(`${institutionToken}-faculty`);
                if (!facultyDiv) {
                    continue;
                }

                const rows = Array.from(facultyDiv.querySelectorAll('tr')).slice(1);
                for (const row of rows) {
                    if (candidates.length >= maxEntries) {
                        break;
                    }

                    const nameLink = row.querySelector("a[title*='home page']");

                    const rawName = nameLink?.textContent || '';
                    const name = rawName.trim();
                    if (!name) {
                        continue;
                    }

                    const profileUrl = nameLink?.getAttribute('href') || null;
                    candidates.push({
                        name,
                        raw_name: rawName,
                        university,
                        raw_university: rawUniversity,
                        profile_url: profileUrl,
                    });
                }

                if (window.csr && typeof window.csr.toggleFaculty === 'function') {
                    window.csr.toggleFaculty(institutionToken);
                }
            }

            return {
                candidates,
                widget_count: widgetSpans.length,
            };
        }""",
        limit,
    )

    if isinstance(payload, dict) and payload.get("error"):
        logger.warning("Ranking parser error for %s: %s", country, payload["error"])
        return []

    parsed: list[ProfessorCandidate] = []
    raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    for item in raw_candidates:
        name = _clean_professor_name((item.get("name") or "").strip())
        if not name:
            continue
        parsed.append(
            ProfessorCandidate(
                country=country,
                name=name,
                university=(item.get("university") or None),
                profile_url=(item.get("profile_url") or None),
                raw_name=(item.get("raw_name") or None),
                raw_university=(item.get("raw_university") or None),
            )
        )

    logger.info(
        "Extracted %s faculty candidates for %s from %s institution rows",
        len(parsed),
        country,
        payload.get("widget_count") if isinstance(payload, dict) else "unknown",
    )
    return parsed


async def scrape_professors_from_csrankings(
    website: str,
    countries: list[str],
    max_professors_per_country: int,
) -> tuple[list[ProfessorCandidate], ScrapeDiagnostics]:
    candidates: list[ProfessorCandidate] = []
    seen: set[tuple[str, str]] = set()
    base_url = _normalize_website(website)
    diagnostics = ScrapeDiagnostics(
        unsupported_countries=[],
        page_load_failures={},
        countries_with_no_candidates=[],
    )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            for country in countries:
                code = _resolve_country_code(country)
                if not code:
                    diagnostics.unsupported_countries.append(country)
                    logger.info("Skipping unsupported country for ranking source: %s", country)
                    continue

                target_url = f"{base_url}&{code}"
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
                    await page.wait_for_selector("table#ranking", timeout=45_000)
                    await asyncio.sleep(0.75)
                except Exception as exc:
                    logger.warning("Failed loading ranking page for %s: %s", country, exc)
                    diagnostics.page_load_failures[country] = str(exc)
                    continue

                country_candidates = await _extract_candidates_from_ranking_table(
                    page=page,
                    country=country,
                    limit=max_professors_per_country,
                )

                if not country_candidates:
                    diagnostics.countries_with_no_candidates.append(country)
                    logger.info("No faculty entries found on ranking page for country: %s", country)
                    continue

                for candidate in country_candidates:
                    dedupe_key = (country.lower(), candidate.name.lower())
                    if dedupe_key in seen:
                        continue

                    seen.add(dedupe_key)
                    candidates.append(candidate)
        finally:
            await browser.close()

    logger.info("Ranking scraping completed with %s candidates", len(candidates))
    return candidates, diagnostics
