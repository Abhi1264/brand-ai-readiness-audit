from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from brand_ai_readiness.models.report import AuditReport
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from brand_ai_readiness.orchestration.validate import validate_report_payload
from tests.helpers import snapshot_from_site_dir

ROOT = Path(__file__).resolve().parents[1]


def test_required_fields_and_counts():
    snapshot = snapshot_from_site_dir("04_missing_structured")
    report = report_from_snapshot(snapshot)
    payload = report.model_dump_public()
    assert payload["site"]
    assert payload["audited_at"].endswith("Z")
    for field in ("total_findings", "critical", "high", "medium"):
        assert field in payload["summary"]
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in payload["findings"]:
        for key in ("id", "title", "severity", "evidence", "suggested_action"):
            assert key in finding
        assert finding["suggested_action"]["summary"]
        counts[finding["severity"]] += 1
    assert payload["summary"]["total_findings"] == len(payload["findings"])
    assert payload["summary"]["critical"] == counts["critical"]
    assert payload["summary"]["high"] == counts["high"]
    assert payload["summary"]["medium"] == counts["medium"]


def test_schema_rejects_mismatched_counts():
    payload = {
        "site": "x.com",
        "audited_at": datetime.now(timezone.utc),
        "summary": {"total_findings": 2, "critical": 0, "high": 0, "medium": 0, "low": 0},
        "findings": [],
    }
    with pytest.raises(Exception):
        AuditReport.model_validate(payload)


def test_marketplace_has_exactly_one_entrypoint():
    manifest = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))
    entry = [s for s in manifest["skills"] if s.get("entrypoint")]
    assert len(entry) == 1
    assert entry[0]["id"] == "audit-orchestrator"
    for skill in manifest["skills"]:
        skill_md = ROOT / skill["path"] / "SKILL.md"
        assert skill_md.is_file()
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {skill['id']}" in text
        assert "description:" in text


def test_excellent_site_is_not_a_false_positive_storm():
    report = report_from_snapshot(snapshot_from_site_dir("01_excellent"))
    critical = [item for item in report.findings if item.severity == "critical"]
    assert critical == []
    assert report.summary.total_findings <= 6


def _sample_report():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "examples" / "sample-report.json").read_text(encoding="utf-8"))


def test_sample_report_validates():
    report = validate_report_payload(_sample_report())
    assert report.site
    assert report.summary.total_findings == len(report.findings)


def test_sample_report_is_not_stale():
    import json

    from brand_ai_readiness.orchestration.compose import report_from_snapshot
    from tests.helpers import snapshot_from_site_dir

    fresh = json.loads(report_from_snapshot(snapshot_from_site_dir("04_missing_structured")).model_dump_json())
    sample = _sample_report()

    missing_top = set(fresh) - set(sample)
    assert not missing_top, f"sample-report.json is missing top-level keys: {sorted(missing_top)}"

    fresh_keys = set(fresh["findings"][0])
    sample_keys = set().union(*(set(f) for f in sample["findings"]))
    missing_finding = fresh_keys - sample_keys
    assert not missing_finding, f"sample findings are missing keys: {sorted(missing_finding)}"


def test_sample_markdown_matches_the_sample_json():
    from pathlib import Path

    from brand_ai_readiness.orchestration.render_markdown import render_markdown

    root = Path(__file__).resolve().parents[1]
    shipped = (root / "examples" / "sample-report.md").read_text(encoding="utf-8")
    sample = _sample_report()
    for finding in sample["findings"]:
        assert finding["title"] in shipped
    assert render_markdown(sample).startswith("# AI-readiness audit")
