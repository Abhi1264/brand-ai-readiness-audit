from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TypedDict

from brand_ai_readiness.analysis.html import cta_matches, headings, parse_html
from brand_ai_readiness.analysis.pageview import effective_page
from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage, RenderedPage

_IDENTITY = re.compile(
    r"\b(we (are|help|build|provide|make)|platform for|software for|serving|helps? "
    r"(teams|companies|customers|people)|the .+ (for|that))\b",
    re.I,
)
_AUDIENCE = re.compile(
    r"\b(for (teams|developers|marketers|founders|students|patients|shoppers|"
    r"enterprises|small businesses|families)|built for|designed for)\b",
    re.I,
)
_NAV_LABELS = re.compile(r"^(click here|here|link|page|untitled)$", re.I)


@dataclass
class EngagementSignals:
    has_h1: bool = False
    h1_text: str = ""
    identity_statement: bool = False
    audience_statement: bool = False
    cta_texts: list[str] = field(default_factory=list)
    nav_count: int = 0
    confusing_labels: list[str] = field(default_factory=list)
    dead_end_urls: list[str] = field(default_factory=list)
    broken_internal: list[str] = field(default_factory=list)
    missing_next_step: list[str] = field(default_factory=list)
    mobile_issues: list[str] = field(default_factory=list)


class HomepageOrientation(TypedDict):
    has_h1: bool
    h1_text: str
    identity_statement: bool
    audience_statement: bool
    cta_texts: list[str]
    word_count: int


def homepage_orientation(page: FetchedPage) -> HomepageOrientation:
    soup = parse_html(page.html)
    heads = headings(soup)
    h1s = [item["text"] for item in heads if item["level"] == "h1"]
    text = page.text or ""
    return HomepageOrientation(
        has_h1=bool(h1s),
        h1_text=h1s[0] if h1s else "",
        identity_statement=bool(_IDENTITY.search(text)),
        audience_statement=bool(_AUDIENCE.search(text)),
        cta_texts=list(dict.fromkeys(cta_matches(text)))[:8],
        word_count=page.word_count,
    )


def nav_quality(page: FetchedPage) -> tuple[int, list[str]]:
    soup = parse_html(page.html)
    nav = soup.find("nav") or soup.find(attrs={"role": "navigation"})
    labels: list[str] = []
    confusing: list[str] = []
    scope = nav if nav else soup
    for anchor in scope.find_all("a"):
        label = anchor.get_text(" ", strip=True)
        if not label:
            continue
        labels.append(label)
        if _NAV_LABELS.match(label.strip()):
            confusing.append(label)
    return len(labels), confusing


def dead_ends(snapshot: CrawlSnapshot) -> list[str]:
    flagged: list[str] = []
    for page in snapshot.successful_pages():
        if page.role in {"legal", "contact"}:
            continue
        if page.role in {"product", "service", "article", "docs", "landing"} and len(page.internal_links) <= 1:
            flagged.append(page.url)
    return flagged


def broken_internal_links(snapshot: CrawlSnapshot) -> list[str]:
    by_url = {page.url: page for page in snapshot.pages}
    by_final = {page.final_url: page for page in snapshot.pages}
    broken: list[str] = []
    for page in snapshot.pages:
        failed_http = page.fetch_status == "failed" and page.status_code >= 400
        error_status = page.status_code in {404, 410, 500, 502, 503}
        if (failed_http or error_status) and page.url not in broken:
            broken.append(page.url)
    for page in snapshot.successful_pages():
        for link in page.internal_links:
            target = by_url.get(link) or by_final.get(link)
            if target and target.status_code in {404, 410} and link not in broken:
                broken.append(link)
    return broken


def missing_continuation(snapshot: CrawlSnapshot) -> list[str]:
    present_roles = {page.role for page in snapshot.successful_pages()}
    missing: list[str] = []
    homepage = snapshot.homepage()
    if not homepage:
        return missing
    linked_roles = set()
    role_of = {page.url: page.role for page in snapshot.pages}
    for link in homepage.internal_links:
        role = role_of.get(link)
        if role:
            linked_roles.add(role)
    if snapshot.site_type in {"saas", "ecommerce"} and "pricing" in present_roles and "pricing" not in linked_roles:
        missing.append("homepage does not link to an observed pricing page")
    if "contact" in present_roles and "contact" not in linked_roles and not cta_matches(homepage.text):
        missing.append("homepage does not link to contact and has no CTA phrasing")
    if snapshot.site_type == "ecommerce" and "product" in present_roles and "product" not in linked_roles:
        missing.append("homepage does not link to observed product pages")
    return missing


def mobile_issues(rendered: list[RenderedPage]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for page in rendered:
        if page.viewport != "mobile" or page.error:
            continue
        problems: list[str] = []
        if page.overflow_x:
            problems.append("horizontal_overflow")
        if page.min_font_px is not None and page.min_font_px < 11:
            problems.append("unreadable_text")
        if not page.nav_visible:
            problems.append("navigation_not_visible")
        if not page.cta_visible:
            desktop = next(
                (item for item in rendered if item.url == page.url and item.viewport == "desktop" and not item.error),
                None,
            )
            if desktop and desktop.cta_visible:
                problems.append("cta_disappeared_on_mobile")
        if problems:
            issues.append({"url": page.url, "problems": problems})
    return issues


def analyze_engagement(snapshot: CrawlSnapshot) -> EngagementSignals:
    homepage = snapshot.homepage()
    if homepage:
        homepage = effective_page(homepage, snapshot)
    signals = EngagementSignals()
    if homepage:
        orient = homepage_orientation(homepage)
        signals.has_h1 = orient["has_h1"]
        signals.h1_text = orient["h1_text"]
        signals.identity_statement = orient["identity_statement"]
        signals.audience_statement = orient["audience_statement"]
        signals.cta_texts = orient["cta_texts"]
        nav_count, confusing = nav_quality(homepage)
        signals.nav_count = nav_count
        signals.confusing_labels = confusing
    signals.dead_end_urls = dead_ends(snapshot)
    signals.broken_internal = broken_internal_links(snapshot)
    signals.missing_next_step = missing_continuation(snapshot)
    signals.mobile_issues = [f"{item['url']}: {', '.join(item['problems'])}" for item in mobile_issues(snapshot.rendered)]
    return signals
