"""Internal finding model used by every skill analyzer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from brand_ai_readiness.models.evidence import EvidencePayload

Severity = Literal["critical", "high", "medium", "low"]
Priority = Literal["critical", "high", "medium", "low"]
Category = Literal[
    "crawlability",
    "rendering",
    "machine_readability",
    "structured_data",
    "entity",
    "freshness",
    "corroboration",
    "engagement",
    "mobile",
    "coverage",
]


class SuggestedAction(BaseModel):
    summary: str
    details: str = ""
    priority: Priority = "medium"
    rationale: str = ""
    implementation_direction: str = ""

    @field_validator("summary")
    @classmethod
    def summary_must_be_specific(cls, value: str) -> str:
        text = value.strip()
        if len(text) < 8:
            raise ValueError("suggested_action.summary must be specific")
        return text


class Finding(BaseModel):
    """Full internal finding. Public report fields are a projection of this."""

    id: str
    category: Category
    title: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: EvidencePayload
    mechanism: str
    mechanism_code: str
    impact: str
    suggested_action: SuggestedAction
    source_urls: list[str] = Field(default_factory=list)
    scope_pages: int = 0
    scope_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    impact_weight: int = Field(default=2, ge=1, le=4)

    def evidence_text(self) -> str:
        return self.evidence.as_text()

    def public_dict(self, public_id: str) -> dict[str, Any]:
        action = {
            "summary": self.suggested_action.summary,
            "priority": self.suggested_action.priority,
        }
        if self.suggested_action.details:
            action["details"] = self.suggested_action.details
        if self.suggested_action.rationale:
            action["rationale"] = self.suggested_action.rationale
        if self.suggested_action.implementation_direction:
            action["implementation_direction"] = self.suggested_action.implementation_direction
        return {
            "id": public_id,
            "title": self.title,
            "severity": self.severity,
            "evidence": self.evidence_text(),
            "suggested_action": action,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "mechanism": self.mechanism,
            "impact": self.impact,
            "source_urls": list(self.source_urls),
        }


class PublicFinding(BaseModel):
    """Minimum required public finding plus useful extras."""

    id: str
    title: str
    severity: Severity
    evidence: str
    suggested_action: SuggestedAction
    category: Category | None = None
    confidence: float | None = None
    mechanism: str | None = None
    impact: str | None = None
    source_urls: list[str] = Field(default_factory=list)
