"""Validated final audit report — contest-required floor plus extras."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from brand_ai_readiness.models.findings import PublicFinding, Severity


class SeveritySummary(BaseModel):
    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

    @model_validator(mode="after")
    def totals_must_match(self) -> SeveritySummary:
        counted = self.critical + self.high + self.medium + self.low
        if self.total_findings != counted:
            raise ValueError(
                f"summary.total_findings ({self.total_findings}) != "
                f"severity counts ({counted})"
            )
        return self


class ProactiveRecommendation(BaseModel):
    summary: str
    why_it_matters: str
    what_to_change: str
    expected_benefit: str
    priority: str = "medium"


class Scorecard(BaseModel):
    """Observable-signal scores. Each component is documented in scoring/scorecard.py."""

    ai_discoverability_score: int = Field(ge=0, le=100)
    engagement_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    components: dict[str, int] = Field(default_factory=dict)
    formula: str


class Coverage(BaseModel):
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_rendered: int = 0
    pages_failed: int = 0
    pages_blocked: int = 0
    rendering_status: str = "skipped"
    corroboration_status: str = "unavailable"
    limitations: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    site: str
    audited_at: datetime
    summary: SeveritySummary
    findings: list[PublicFinding] = Field(default_factory=list)
    proactive_recommendations: list[ProactiveRecommendation] = Field(default_factory=list)
    crawl_statistics: dict[str, Any] = Field(default_factory=dict)
    coverage: Coverage = Field(default_factory=Coverage)
    scores: Scorecard | None = None
    site_type: str | None = None

    @field_validator("site")
    @classmethod
    def site_not_empty(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("site must be a hostname")
        return host

    @field_validator("audited_at")
    @classmethod
    def audited_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @model_validator(mode="after")
    def findings_match_summary(self) -> AuditReport:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in self.findings:
            counts[finding.severity] += 1
        expected = SeveritySummary(
            total_findings=len(self.findings),
            critical=counts["critical"],
            high=counts["high"],
            medium=counts["medium"],
            low=counts["low"],
        )
        if self.summary != expected:
            raise ValueError("summary counts do not match findings")
        ids = [item.id for item in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("finding ids must be unique")
        required = {"id", "title", "severity", "evidence"}
        for finding in self.findings:
            if not finding.suggested_action.summary:
                raise ValueError("each finding needs suggested_action.summary")
            missing = required - set(finding.model_dump())
            if missing:
                raise ValueError(f"finding missing {missing}")
        return self

    def model_dump_public(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["audited_at"] = self.audited_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return payload
