from __future__ import annotations

import re
from dataclasses import dataclass, field

from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage

_CHALLENGE_TITLES = re.compile(
    r"\b("
    r"access denied|just a moment|attention required|are you a (?:robot|human)|"
    r"verify (?:you are|your) human|security check|bot (?:detection|verification)|"
    r"request (?:blocked|unsuccessful)|pardon our interruption|checking your browser|"
    r"human verification|forbidden|blocked"
    r")\b",
    re.I,
)

_BODY_MARKERS = (
    "cf-browser-verification",
    "challenge-platform",
    "cf_chl_",
    "_incapsula_",
    "incap_ses_",
    "distil_r_captcha",
    "px-captcha",
    "perimeterx",
    "recaptcha",
    "hcaptcha",
    "enable javascript and cookies to continue",
    "ray id",
)

_HEADER_MARKERS = ("cf-mitigated", "cf-chl-bypass", "x-datadome", "x-iinfo")

BLOCKING_STATUS = frozenset({401, 403, 405, 406, 429, 503})
_THIN_WORDS = 60


@dataclass
class BlockAssessment:
    is_blocked: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "; ".join(self.reasons)


def assess_block(
    *,
    status_code: int,
    html: str,
    text: str,
    title: str | None,
    word_count: int,
    headers: dict[str, str] | None = None,
) -> BlockAssessment:
    reasons: list[str] = []
    lowered_html = (html or "").lower()
    haystack = f"{title or ''} {text or ''}".strip()

    header_hit = next(
        (key for key in (headers or {}) if key.lower() in _HEADER_MARKERS),
        None,
    )
    if header_hit:
        reasons.append(f"edge-intervention header '{header_hit}'")

    title_match = _CHALLENGE_TITLES.search(haystack[:400]) if haystack else None
    if title_match:
        reasons.append(f"challenge wording {title_match.group(0)!r}")

    body_hit = next((marker for marker in _BODY_MARKERS if marker in lowered_html), None)
    if body_hit:
        reasons.append(f"challenge marker {body_hit!r} in the body")

    blocking_status = status_code in BLOCKING_STATUS
    if blocking_status:
        reasons.append(f"HTTP {status_code}")

    # Vendor markers convict alone. Generic wording needs a second signal.
    strong = bool(header_hit or body_hit)
    corroborated = bool(title_match) and (blocking_status or word_count < _THIN_WORDS)
    return BlockAssessment(is_blocked=strong or corroborated, reasons=reasons)


def assess_page(page: FetchedPage) -> BlockAssessment:
    return assess_block(
        status_code=page.status_code,
        html=page.html,
        text=page.text,
        title=page.title,
        word_count=page.word_count,
        headers=page.headers,
    )


def blocked_pages(snapshot: CrawlSnapshot) -> list[tuple[FetchedPage, BlockAssessment]]:
    out = []
    for page in snapshot.pages:
        assessment = assess_page(page)
        if assessment.is_blocked:
            out.append((page, assessment))
    return out


def homepage_content_unusable(snapshot: CrawlSnapshot) -> str | None:
    home = snapshot.homepage()
    if home is None:
        return "no homepage was fetched"
    blocked = assess_page(home)
    if blocked.is_blocked:
        return f"the homepage returned a bot-challenge page ({blocked.summary})"
    if home.fetch_status != "success":
        detail = f"HTTP {home.status_code}" if home.status_code else (home.error or "fetch failed")
        return f"the homepage was not fetched successfully ({detail})"
    return None
