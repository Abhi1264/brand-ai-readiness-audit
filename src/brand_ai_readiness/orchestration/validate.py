from __future__ import annotations

from typing import Any

from brand_ai_readiness.models.report import AuditReport


REQUIRED_REPORT_FIELDS = ("site", "audited_at", "summary", "findings")
REQUIRED_FINDING_FIELDS = ("id", "title", "severity", "evidence", "suggested_action")
REQUIRED_SUMMARY_FIELDS = ("total_findings", "critical", "high", "medium")


def validate_report_payload(payload: dict[str, Any]) -> AuditReport:
    missing = [field for field in REQUIRED_REPORT_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"report missing {missing}")
    summary = payload.get("summary") or {}
    for field in REQUIRED_SUMMARY_FIELDS:
        if field not in summary:
            raise ValueError(f"summary missing {field}")
    for finding in payload.get("findings") or []:
        for field in REQUIRED_FINDING_FIELDS:
            if field not in finding:
                raise ValueError(f"finding {finding.get('id')} missing {field}")
        action = finding.get("suggested_action")
        if not isinstance(action, dict) or "summary" not in action:
            raise ValueError("suggested_action.summary is required")
    return AuditReport.model_validate(payload)
