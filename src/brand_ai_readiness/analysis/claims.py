from __future__ import annotations

import re
from typing import Literal

from brand_ai_readiness.models.snapshot import CrawlSnapshot, ExtractedClaim

ClaimImportance = Literal["high", "medium", "low"]

_PATTERNS: list[tuple[str, ClaimImportance, re.Pattern[str]]] = [
    ("founding", "high", re.compile(r"\b(?:founded|established|since)\s+(?:in\s+)?((?:19|20)\d{2})\b", re.I)),
    ("headquarters", "high", re.compile(r"\b(?:headquartered|headquarters|based)\s+in\s+([A-Z][^.]{2,60})", re.I)),
    ("leadership", "medium", re.compile(r"\b(?:CEO|founder|president|director)\b[:,]?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.I)),
    ("pricing", "high", re.compile(r"\b(?:starts? at|priced at|from)\s+(\$?\d[\d,]*(?:\.\d{2})?)", re.I)),
    ("award", "low", re.compile(r"\b((?:award|certified|certification|accredited)[^.]{0,80})", re.I)),
    ("statistic", "medium", re.compile(r"\b(\d{1,3}%\s+[^.]+)", re.I)),
]


def extract_claims(snapshot: CrawlSnapshot) -> CrawlSnapshot:
    claims: list[ExtractedClaim] = []
    seen: set[str] = set()
    pages = snapshot.successful_pages()
    important = [page for page in pages if page.role in {"homepage", "about", "product", "pricing", "service"}]
    if not important:
        important = pages[:5]
    for page in important:
        text = page.text or ""
        for kind, importance, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0).strip()
                key = snippet.lower()
                if key in seen or len(snippet) < 6:
                    continue
                seen.add(key)
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                evidence = text[start:end].strip()
                claims.append(
                    ExtractedClaim(
                        claim=snippet,
                        source_url=page.url,
                        source_page=page.title or page.role,
                        evidence_text=evidence[:280],
                        importance=importance,
                        freshness_signal="none",
                        entity=kind,
                    )
                )
    snapshot.claims = claims
    return snapshot
