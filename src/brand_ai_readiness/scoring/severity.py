"""Deterministic severity from impact, scope, and confidence."""

from __future__ import annotations

from brand_ai_readiness.models.findings import Finding, Severity

RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def score_severity(impact_weight: int, scope_fraction: float, confidence: float) -> Severity:
    """
    impact_weight: 1 (minor) .. 4 (fundamental barrier)
    scope_fraction: 0..1 share of relevant pages
    confidence: 0..1 observational confidence
    """
    scope = min(max(scope_fraction, 0.0), 1.0)
    conf = min(max(confidence, 0.0), 1.0)
    raw = impact_weight * 22 * (0.45 + 0.55 * scope) * (0.55 + 0.45 * conf)
    if impact_weight >= 4 and conf >= 0.8 and raw >= 70:
        return "critical"
    if raw >= 58 or (impact_weight >= 3 and scope >= 0.5 and conf >= 0.75):
        return "high"
    if raw >= 32:
        return "medium"
    return "low"


def apply_severity(finding: Finding) -> Finding:
    finding.severity = score_severity(finding.impact_weight, finding.scope_fraction, finding.confidence)
    if RANK[finding.suggested_action.priority] < RANK[finding.severity]:
        finding.suggested_action.priority = finding.severity
    return finding
