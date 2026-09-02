from __future__ import annotations

import re
from collections import Counter

from brand_ai_readiness.analysis.pageview import effective_page
from brand_ai_readiness.models.snapshot import CrawlSnapshot, SiteType

# Commit only when a type wins by this margin; otherwise the site is mixed.
_SITE_TYPE_MARGIN = 2

_SIGNAL_RULES: list[tuple[SiteType, str, re.Pattern[str]]] = [
    ("ecommerce", "product/price vocabulary", re.compile(r"\b(add to cart|buy now|sku|in stock|checkout)\b", re.I)),
    ("saas", "saas vocabulary", re.compile(r"\b(sign up|start free|api|dashboard|workspace|subscription)\b", re.I)),
    ("docs", "documentation vocabulary", re.compile(r"\b(documentation|getting started|api reference|guides)\b", re.I)),
    ("article", "publication vocabulary", re.compile(r"\b(published|byline|newsletter|journalist|op-ed)\b", re.I)),
    ("local_business", "local vocabulary", re.compile(r"\b(hours|reservations|visit us|directions|store locator)\b", re.I)),
    ("nonprofit", "nonprofit vocabulary", re.compile(r"\b(donate|nonprofit|mission|volunteer|501c)\b", re.I)),
    ("university", "university vocabulary", re.compile(r"\b(admissions|campus|faculty|undergraduate|alumni)\b", re.I)),
    ("corporate", "corporate vocabulary", re.compile(r"\b(investors|careers|about us|our company|leadership)\b", re.I)),
]


def infer_site_type(snapshot: CrawlSnapshot) -> CrawlSnapshot:
    scores: dict[SiteType, int] = {}
    signals: list[str] = []
    homepage = snapshot.homepage()
    if homepage:
        homepage = effective_page(homepage, snapshot)
    corpus = " ".join(
        part
        for part in [
            homepage.text if homepage else "",
            homepage.title if homepage else "",
            " ".join(page.role for page in snapshot.pages),
        ]
        if part
    )
    role_bonus = {
        "product": ("ecommerce", 2, "product pages present"),
        "pricing": ("saas", 2, "pricing page present"),
        "article": ("article", 2, "article/blog pages present"),
        "docs": ("docs", 2, "docs pages present"),
        "contact": ("local_business", 1, "contact/location pages present"),
    }
    # Score each role once, scaled by crawl share, so one URL family cannot dominate.
    role_counts = Counter(page.role for page in snapshot.pages)
    total_pages = max(len(snapshot.pages), 1)
    for role, (kind, weight, label) in role_bonus.items():
        count = role_counts.get(role, 0)
        if not count:
            continue
        dominant = count / total_pages >= 0.5
        scores[kind] = scores.get(kind, 0) + weight + (1 if dominant else 0)
        signal = f"{label} ({count}/{total_pages} crawled pages)"
        if signal not in signals:
            signals.append(signal)
    for kind, label, pattern in _SIGNAL_RULES:
        if pattern.search(corpus):
            scores[kind] = scores.get(kind, 0) + 2
            signals.append(label)

    if not scores:
        snapshot.site_type = "unknown"
        snapshot.site_type_signals = signals
        return snapshot

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, top = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if top - runner_up < _SITE_TYPE_MARGIN:
        snapshot.site_type = "mixed"
    else:
        snapshot.site_type = winner
    snapshot.site_type_signals = signals
    return snapshot


def expected_schema_types(site_type: SiteType) -> list[str]:
    common = ["Organization", "WebSite"]
    extra = {
        "ecommerce": ["Product", "Offer", "BreadcrumbList"],
        "saas": ["SoftwareApplication", "Organization", "WebSite"],
        "article": ["Article", "BreadcrumbList"],
        "docs": ["TechArticle", "WebSite"],
        "local_business": ["LocalBusiness", "PostalAddress"],
        "nonprofit": ["NGO", "Organization"],
        "university": ["CollegeOrUniversity", "Organization"],
        "corporate": ["Organization", "WebSite"],
        "mixed": ["Organization", "WebSite"],
        "unknown": ["Organization", "WebSite"],
    }
    return list(dict.fromkeys(common + extra.get(site_type, [])))
