from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil import parser as dateparse

from brand_ai_readiness.analysis.html import meta_content, parse_html
from brand_ai_readiness.models.snapshot import FetchedPage

_VISIBLE_DATE = re.compile(
    r"\b(?:published|updated|modified|last\s+updated|posted)\b[:\s]+([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)
_COPYRIGHT = re.compile(r"©\s*((?:19|20)\d{2})|\bcopyright\s+((?:19|20)\d{2})", re.I)
_TIME_SENSITIVE = re.compile(
    r"\b(pricing|price|now|current|this year|latest|announcing|breaking|rate|discount)\b",
    re.I,
)


@dataclass
class FreshnessSignal:
    url: str
    date_published: str | None = None
    date_modified: str | None = None
    visible_date: str | None = None
    copyright_year: str | None = None
    parsed_modified: datetime | None = None
    time_sensitive: bool = False
    status: str = "freshness_cannot_be_established"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dateparse.parse(value, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def page_freshness(page: FetchedPage, structured_dates: dict[str, str] | None = None) -> FreshnessSignal:
    structured = structured_dates or {}
    published = structured.get("datePublished")
    modified = structured.get("dateModified")
    if not published or not modified:
        soup = parse_html(page.html)
        if not published:
            published = meta_content(soup, "article:published_time", "datePublished", "pubdate", "date")
        if not modified:
            modified = meta_content(soup, "article:modified_time", "dateModified", "og:updated_time")
    visible = None
    match = _VISIBLE_DATE.search(page.text or "")
    if match:
        visible = match.group(1)
    copyright_year = None
    copy_match = _COPYRIGHT.search(page.text or "")
    if copy_match:
        copyright_year = copy_match.group(1) or copy_match.group(2)
    parsed = _parse_date(modified) or _parse_date(visible) or _parse_date(published)
    time_sensitive = bool(_TIME_SENSITIVE.search(page.text or ""))
    status = "freshness_cannot_be_established"
    if parsed:
        age_days = (datetime.now(timezone.utc) - parsed).days
        if time_sensitive and age_days > 365 * 2:
            status = "stale_time_sensitive"
        else:
            status = "dated"
    signal = FreshnessSignal(
        url=page.url,
        date_published=published,
        date_modified=modified,
        visible_date=visible,
        copyright_year=copyright_year,
        parsed_modified=parsed,
        time_sensitive=time_sensitive,
        status=status,
    )
    return signal
