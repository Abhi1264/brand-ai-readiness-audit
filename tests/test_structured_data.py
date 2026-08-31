from __future__ import annotations

from brand_ai_readiness.analysis.checks_structured import structured_findings
from brand_ai_readiness.analysis.html import json_ld_blocks, parse_html
from brand_ai_readiness.analysis.site_type import infer_site_type
from brand_ai_readiness.analysis.structured import collect_structured
from brand_ai_readiness.orchestration.compose import enrich_snapshot, report_from_snapshot
from tests.helpers import snapshot_from_site_dir


def test_valid_jsonld_parses():
    html = '<script type="application/ld+json">{"@type":"Organization","name":"A"}</script>'
    parsed, error = json_ld_blocks(parse_html(html))[0]
    assert error is None
    assert parsed["name"] == "A"


def test_malformed_jsonld_is_recorded():
    html = '<script type="application/ld+json">{name: nope}</script>'
    parsed, error = json_ld_blocks(parse_html(html))[0]
    assert parsed is None
    assert error


def test_missing_structured_data_site():
    snapshot = snapshot_from_site_dir("04_missing_structured")
    enrich_snapshot(snapshot)
    codes = {item.mechanism_code for item in structured_findings(snapshot)}
    assert "missing_jsonld" in codes


def test_conflicting_structured_data_site():
    snapshot = snapshot_from_site_dir("05_conflicting_structured")
    enrich_snapshot(snapshot)
    codes = {item.mechanism_code for item in structured_findings(snapshot)}
    assert "structured_visible_mismatch" in codes


def test_excellent_site_has_organization():
    snapshot = snapshot_from_site_dir("01_excellent")
    collect_structured(snapshot)
    infer_site_type(snapshot)
    types = {t for block in snapshot.structured for t in block.types}
    assert "Organization" in types
    assert "missing_jsonld" not in {item.mechanism_code for item in structured_findings(snapshot)}


def test_does_not_demand_faq_schema():
    snapshot = snapshot_from_site_dir("01_excellent")
    report = report_from_snapshot(snapshot)
    titles = " ".join(item.title.lower() for item in report.findings)
    assert "faq" not in titles
