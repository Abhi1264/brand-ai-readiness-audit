"""Recognise bot-challenge and access-denied pages.

A WAF or CDN that refuses a crawler usually answers with a page rather than a
bare status: "Access Denied", "Just a moment...", a CAPTCHA, a Ray ID. It is
HTML, it parses, and every content check will happily analyse it -- reporting a
missing H1, absent structured data and a weak value proposition for a page the
brand never served.

Those findings are all false. The real finding is that the origin served a
challenge, which is a discoverability problem in its own right and the only
thing that can honestly be said about a site whose content was never seen.

Detection is deliberately conservative: a blocking status alone is not enough,
because a 403 can be an ordinary permissions error on one URL, and a short page
alone is not enough, because thin pages exist. A marker plus corroborating
evidence is required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Phrases that appear in the title or first heading of a challenge page.
_CHALLENGE_TITLES = re.compile(
    r"\b("
    r"access denied|just a moment|attention required|are you a (?:robot|human)|"
    r"verify (?:you are|your) human|security check|bot (?:detection|verification)|"
    r"request (?:blocked|unsuccessful)|pardon our interruption|checking your browser|"
    r"human verification|forbidden|blocked"
    r")\b",
    re.I,
)

# Vendor markers in the response body.
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

# Response headers that only appear when an edge decided to intervene.
_HEADER_MARKERS = ("cf-mitigated", "cf-chl-bypass", "x-datadome", "x-iinfo")

BLOCKING_STATUS = frozenset({401, 403, 405, 406, 429, 503})

# Below this, a page carries no usable content regardless of what it claims.
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
    """Decide whether a response is a challenge page rather than real content."""
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

    # A marker on its own is enough only when it is vendor-specific. Generic
    # wording needs a second signal, so an article *about* access denial is not
    # mistaken for a block.
    strong = bool(header_hit or body_hit)
    corroborated = bool(title_match) and (blocking_status or word_count < _THIN_WORDS)
    return BlockAssessment(is_blocked=strong or corroborated, reasons=reasons)


def assess_page(page) -> BlockAssessment:  # noqa: ANN001 - FetchedPage, avoids a cycle
    return assess_block(
        status_code=page.status_code,
        html=page.html,
        text=page.text,
        title=page.title,
        word_count=page.word_count,
        headers=page.headers,
    )


def blocked_pages(snapshot) -> list[tuple]:  # noqa: ANN001 - CrawlSnapshot
    out = []
    for page in snapshot.pages:
        assessment = assess_page(page)
        if assessment.is_blocked:
            out.append((page, assessment))
    return out


def homepage_is_blocked(snapshot) -> BlockAssessment | None:  # noqa: ANN001
    home = snapshot.homepage()
    if home is None:
        return None
    assessment = assess_page(home)
    return assessment if assessment.is_blocked else None


def homepage_content_unusable(snapshot) -> str | None:  # noqa: ANN001
    """Why the homepage's content cannot be analysed, or None if it can.

    A challenge page is one way to receive no content; a 404, an error body or a
    near-empty response are others. In every case the content skills would be
    describing something the brand never served, so the distinction that matters
    is "was real content received", not "why not".
    """
    home = snapshot.homepage()
    if home is None:
        return "no homepage was fetched"
    blocked = assess_page(home)
    if blocked.is_blocked:
        return f"the homepage returned a bot-challenge page ({blocked.summary})"
    if home.fetch_status != "success":
        detail = f"HTTP {home.status_code}" if home.status_code else (home.error or "fetch failed")
        return f"the homepage was not fetched successfully ({detail})"
    # A thin page that WAS served is a real engagement finding, not a reason to
    # skip the checks -- suppressing it would hide the very defect being audited.
    return None
