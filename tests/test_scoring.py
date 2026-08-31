from __future__ import annotations

from brand_ai_readiness.models.findings import Finding
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from brand_ai_readiness.orchestration.dedupe import dedupe_findings
from brand_ai_readiness.scoring.scorecard import compute_scorecard
from brand_ai_readiness.scoring.severity import score_severity
from tests.helpers import snapshot_from_site_dir


def test_severity_uses_impact_scope_confidence():
    assert score_severity(4, 1.0, 0.95) == "critical"
    assert score_severity(3, 0.6, 0.8) in {"high", "critical"}
    assert score_severity(1, 0.1, 0.5) == "low"


def test_excellent_scores_higher_than_weak_engagement():
    excellent = compute_scorecard(snapshot_from_site_dir("01_excellent"))
    weak = compute_scorecard(snapshot_from_site_dir("10_strong_disco_weak_engagement"))
    assert excellent.engagement_score > weak.engagement_score
    assert 0 <= excellent.overall_score <= 100


def test_dedup_merges_same_mechanism():
    from brand_ai_readiness.analysis.finding_factory import make_finding

    a = make_finding(
        id="CR-011",
        category="crawlability",
        title="Broken internal links were observed during the crawl",
        mechanism_code="broken_internal_links",
        mechanism="x",
        impact="y",
        observation="one",
        source_urls=["https://a.test/x"],
        action_summary="Fix or redirect the broken internal targets and remove stale hrefs.",
        confidence=0.9,
        scope_pages=1,
        scope_fraction=0.2,
        impact_weight=2,
    )
    b = make_finding(
        id="EG-005",
        category="engagement",
        title="Visitors are sent to broken internal URLs",
        mechanism_code="broken_internal_links",
        mechanism="x",
        impact="y",
        observation="two",
        source_urls=["https://a.test/x"],
        action_summary="Redirect or rewrite the broken hrefs to live pages.",
        confidence=0.9,
        scope_pages=1,
        scope_fraction=0.2,
        impact_weight=2,
    )
    merged = dedupe_findings([a, b])
    assert len(merged) == 1
    assert isinstance(merged[0], Finding)


def test_image_only_facts_detected():
    report = report_from_snapshot(snapshot_from_site_dir("08_image_only_facts"))
    assert any("image" in item.title.lower() or "image" in item.evidence.lower() for item in report.findings)
