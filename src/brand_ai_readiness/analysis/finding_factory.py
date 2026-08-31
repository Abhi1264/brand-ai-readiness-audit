"""Shared constructor for evidence-backed findings."""

from __future__ import annotations

from typing import Any

from brand_ai_readiness.models.evidence import EvidencePayload
from brand_ai_readiness.models.findings import Category, Finding, SuggestedAction
from brand_ai_readiness.scoring.severity import apply_severity


def make_finding(
    *,
    id: str,
    category: Category,
    title: str,
    mechanism_code: str,
    mechanism: str,
    impact: str,
    observation: str,
    source_urls: list[str],
    metrics: dict[str, Any] | None = None,
    quotes: list[str] | None = None,
    notes: list[str] | None = None,
    action_summary: str,
    action_details: str = "",
    rationale: str = "",
    implementation_direction: str = "",
    confidence: float,
    scope_pages: int,
    scope_fraction: float,
    impact_weight: int,
) -> Finding:
    finding = Finding(
        id=id,
        category=category,
        title=title,
        severity="medium",
        confidence=confidence,
        evidence=EvidencePayload(
            observation=observation,
            source_urls=source_urls,
            metrics=metrics or {},
            quotes=quotes or [],
            notes=notes or [],
        ),
        mechanism=mechanism,
        mechanism_code=mechanism_code,
        impact=impact,
        suggested_action=SuggestedAction(
            summary=action_summary,
            details=action_details,
            priority="medium",
            rationale=rationale,
            implementation_direction=implementation_direction,
        ),
        source_urls=source_urls,
        scope_pages=scope_pages,
        scope_fraction=min(max(scope_fraction, 0.0), 1.0),
        impact_weight=impact_weight,
    )
    return apply_severity(finding)
