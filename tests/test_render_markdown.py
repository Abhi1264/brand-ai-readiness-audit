from __future__ import annotations

import json

from brand_ai_readiness.orchestration.render_markdown import render_markdown
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from tests.helpers import snapshot_from_site_dir

REPORT = {
    "site": "example.com",
    "audited_at": "2026-09-20T14:32:00Z",
    "site_type": "ecommerce",
    "summary": {"total_findings": 2, "critical": 1, "high": 0, "medium": 0, "low": 1},
    "findings": [
        {
            "id": "F-002",
            "title": "A low severity thing",
            "severity": "low",
            "evidence": "Seen on 1 of 4 pages.",
            "suggested_action": {"summary": "Do the small fix.", "priority": "low"},
        },
        {
            "id": "F-001",
            "title": "A critical thing",
            "severity": "critical",
            "evidence": "Seen on 4 of 4 pages. Observed on: https://example.com/.",
            "suggested_action": {
                "summary": "Do the important fix.",
                "priority": "critical",
                "details": "Longer explanation.",
                "implementation_direction": "In the template.",
            },
            "category": "crawlability",
            "confidence": 0.9,
            "mechanism": "Because of X.",
            "impact": "Costs Y.",
            "source_urls": ["https://example.com/"],
        },
    ],
    "proactive_recommendations": [
        {
            "summary": "An opportunity",
            "why_it_matters": "Because.",
            "what_to_change": "This.",
            "expected_benefit": "That.",
        }
    ],
    "coverage": {
        "pages_crawled": 4,
        "pages_discovered": 9,
        "pages_rendered": 0,
        "rendering_status": "skipped",
        "corroboration_status": "unavailable",
        "access_probe_status": "complete",
        "limitations": ["Rendering was skipped."],
    },
    "scores": {
        "ai_discoverability_score": 70,
        "engagement_score": 60,
        "overall_score": 65,
        "components": {"crawlability": 80},
        "formula": "x",
    },
}


def test_most_severe_finding_comes_first():
    """The reader must be able to start at the top and work down."""
    md = render_markdown(REPORT)
    assert md.index("A critical thing") < md.index("A low severity thing")
    assert md.index("## Start here") < md.index("## Findings")


def test_every_required_element_is_present():
    md = render_markdown(REPORT)
    for expected in (
        "example.com",
        "2026-09-20 14:32:00 UTC",
        "CRITICAL",
        "Do the important fix.",
        "Because of X.",
        "Costs Y.",
        "Seen on 4 of 4 pages.",
        "In the template.",
        "An opportunity",
        "Rendering was skipped.",
        "AI-crawler probe `complete`",
    ):
        assert expected in md, f"missing from the rendered report: {expected!r}"


def test_source_urls_are_not_repeated_under_the_evidence():
    md = render_markdown(REPORT)
    assert md.count("https://example.com/") == 1


def test_clean_site_still_renders_a_useful_report():
    empty = {**REPORT, "findings": [], "summary": {k: 0 for k in REPORT["summary"]}}
    md = render_markdown(empty)
    assert "No defects were detected" in md
    assert "coverage note" in md


def test_renders_a_real_report_without_error():
    report = report_from_snapshot(snapshot_from_site_dir("01_excellent"))
    md = render_markdown(json.loads(report.model_dump_json()))
    assert md.startswith("# AI-readiness audit")
    assert "never modifies the site" in md
