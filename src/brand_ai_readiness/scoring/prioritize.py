"""Sort findings so the first items are the ones to fix first."""

from __future__ import annotations

from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.scoring.severity import RANK


def sort_findings(findings: list[Finding]) -> list[Finding]:
    def key(item: Finding) -> tuple:
        return (
            -RANK[item.severity],
            -item.scope_fraction,
            -item.confidence,
            -item.impact_weight,
            item.id,
        )

    return sorted(findings, key=key)
