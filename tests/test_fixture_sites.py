from __future__ import annotations

from brand_ai_readiness.analysis.checks_crawl import crawl_findings
from brand_ai_readiness.orchestration.compose import report_from_snapshot
from brand_ai_readiness.rendering.compare import compare_raw_and_rendered
from tests.helpers import load_site_html, page_from_html, snapshot_from_site_dir
from brand_ai_readiness.analysis.html import visible_text, word_count
from brand_ai_readiness.models.snapshot import RenderedPage


def _codes(site: str) -> set[str]:
    snapshot = snapshot_from_site_dir(site)
    report = report_from_snapshot(snapshot)
    # mechanism_code is internal; recover from title/evidence keywords + category
    return {item.title.lower() + " " + item.evidence.lower() for item in report.findings}


def test_excellent_site_stays_quiet():
    report = report_from_snapshot(snapshot_from_site_dir("01_excellent"))
    assert all(item.severity != "critical" for item in report.findings)


def test_missing_structured_detected():
    report = report_from_snapshot(snapshot_from_site_dir("04_missing_structured"))
    assert any("json-ld" in item.title.lower() for item in report.findings)


def test_conflicting_structured_detected():
    report = report_from_snapshot(snapshot_from_site_dir("05_conflicting_structured"))
    assert any("match" in item.title.lower() or "inconsistent" in item.title.lower() for item in report.findings)


def test_stale_content_detected():
    report = report_from_snapshot(snapshot_from_site_dir("06_stale_content"))
    assert any("two years" in item.title.lower() or "freshness" in item.category for item in report.findings)


def test_ambiguous_entity_detected():
    report = report_from_snapshot(snapshot_from_site_dir("07_ambiguous_entity"))
    assert any("entity" in (item.category or "") or "name" in item.title.lower() for item in report.findings)


def test_image_only_facts_detected():
    snapshot = snapshot_from_site_dir("08_image_only_facts")
    findings = crawl_findings(snapshot)
    assert any(item.mechanism_code == "image_only_facts" for item in findings)


def test_broken_navigation_detected():
    report = report_from_snapshot(snapshot_from_site_dir("09_broken_navigation"))
    assert any("dead" in item.title.lower() or "label" in item.title.lower() for item in report.findings)


def test_js_only_compare_uses_fixture_pair():
    raw = load_site_html("03_js_only", "index.html")
    rendered_html = load_site_html("03_js_only", "rendered.html")
    page = page_from_html("https://fixture.test/", raw, role="homepage")
    rendered = RenderedPage(
        url=page.url,
        html=rendered_html,
        visible_text=visible_text(rendered_html),
        word_count=word_count(visible_text(rendered_html)),
    )
    assert compare_raw_and_rendered(page, rendered).meaningful


def test_disco_vs_engagement_split():
    strong_disco = report_from_snapshot(snapshot_from_site_dir("10_strong_disco_weak_engagement"))
    weak_disco = report_from_snapshot(snapshot_from_site_dir("11_weak_disco_strong_engagement"))
    assert any(item.category == "engagement" for item in strong_disco.findings)
    assert any(item.category in {"crawlability", "structured_data"} for item in weak_disco.findings)
    assert any("noindex" in item.title.lower() for item in weak_disco.findings)
