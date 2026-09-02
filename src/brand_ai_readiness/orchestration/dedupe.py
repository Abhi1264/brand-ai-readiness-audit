from __future__ import annotations

from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.scoring.severity import RANK


def _merge(primary: Finding, extra: Finding) -> Finding:
    urls = list(dict.fromkeys(primary.source_urls + extra.source_urls))
    notes = list(primary.evidence.notes)
    notes.append(f"Also observed via {extra.id}: {extra.title}")
    primary.source_urls = urls
    primary.evidence.source_urls = urls
    primary.evidence.notes = notes
    primary.scope_pages = max(primary.scope_pages, extra.scope_pages)
    primary.scope_fraction = max(primary.scope_fraction, extra.scope_fraction)
    primary.confidence = max(primary.confidence, extra.confidence * 0.95)
    if RANK[extra.severity] > RANK[primary.severity]:
        primary.severity = extra.severity
        primary.impact_weight = max(primary.impact_weight, extra.impact_weight)
    if extra.evidence.metrics:
        primary.evidence.metrics[f"merged_{extra.id}"] = extra.evidence.metrics
    return primary


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    grouped: dict[str, Finding] = {}
    order: list[str] = []
    for finding in findings:
        key = finding.mechanism_code
        if key not in grouped:
            grouped[key] = finding
            order.append(key)
            continue
        grouped[key] = _merge(grouped[key], finding)
    return [grouped[key] for key in order]
