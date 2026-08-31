"""Crawl priority: homepage and commercially important pages first."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from brand_ai_readiness.models.snapshot import PageRole

_ROLE_RULES: list[tuple[PageRole, re.Pattern[str]]] = [
    ("about", re.compile(r"/(about|company|who-we-are|our-story|team)(/|$)", re.I)),
    ("product", re.compile(r"/(product|products|shop|store|catalog|item)(/|$)", re.I)),
    ("service", re.compile(r"/(service|services|solutions|platform|offerings)(/|$)", re.I)),
    ("pricing", re.compile(r"/(pricing|plans|packages)(/|$)", re.I)),
    ("contact", re.compile(r"/(contact|location|locations|store-locator|find-us)(/|$)", re.I)),
    ("docs", re.compile(r"/(docs|documentation|help|support|faq)(/|$)", re.I)),
    ("article", re.compile(r"/(blog|news|article|articles|press|insights)(/|$)", re.I)),
    ("legal", re.compile(r"/(privacy|terms|legal|cookies|gdpr)(/|$)", re.I)),
]


def classify_role(url: str, is_start: bool = False) -> PageRole:
    if is_start:
        path = urlparse(url).path or "/"
        if path in {"", "/"}:
            return "homepage"
    path = urlparse(url).path or "/"
    if path in {"", "/"}:
        return "homepage"
    for role, pattern in _ROLE_RULES:
        if pattern.search(path):
            return role
    return "other"


def url_priority(url: str, *, from_sitemap: bool = False, from_homepage: bool = False) -> int:
    role = classify_role(url)
    base = {
        "homepage": 100,
        "about": 80,
        "product": 75,
        "service": 74,
        "pricing": 70,
        "contact": 65,
        "docs": 50,
        "article": 40,
        "landing": 55,
        "legal": 15,
        "other": 30,
    }[role]
    if from_sitemap:
        base += 8
    if from_homepage:
        base += 12
    depth = urlparse(url).path.count("/")
    return base - min(depth, 6)
