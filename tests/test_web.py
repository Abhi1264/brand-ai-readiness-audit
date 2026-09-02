from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brand_ai_readiness.web import (
    app,
    coverage_view,
    normalize_public_url,
    verdict_copy,
)

SAMPLE_REPORT = Path(__file__).resolve().parents[1] / "examples" / "sample-report.json"


def _scored_sample() -> dict:
    report = json.loads(SAMPLE_REPORT.read_text())
    report["site_type"] = "corporate"
    report["scores"] = {
        "ai_discoverability_score": 58,
        "engagement_score": 41,
        "overall_score": 50,
        "components": {
            "crawlability": 40,
            "machine_readability": 70,
            "structured_data": 35,
            "entity_clarity": 50,
            "freshness_transparency": 40,
            "homepage_orientation": 45,
            "navigation": 60,
            "cta_clarity": 40,
            "internal_linking": 70,
            "mobile": 60,
        },
        "formula": "test",
    }
    report["findings"][0]["source_urls"] = ["https://example.com/about"]
    report["findings"][0]["impact"] = "Search crawlers cannot read important pages."
    report["findings"][0]["mechanism"] = "robots.txt disallow matched important URLs."
    return report


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_is_html_form():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Check site" in response.text
    assert 'name="url"' in response.text
    assert 'type="text"' in response.text
    assert 'placeholder="example.com"' in response.text
    assert "See what assistants can actually read" in response.text
    assert "Reach" in response.text
    assert "Recommend-only" not in response.text


def test_home_prefills_url():
    response = TestClient(app).get("/?url=example.com")
    assert 'value="example.com"' in response.text


def test_normalize_public_url():
    assert normalize_public_url("example.com") == "https://example.com"
    assert normalize_public_url("https://example.com/about") == "https://example.com/about"
    with pytest.raises(ValueError):
        normalize_public_url("not-a-host")


def test_audit_api_rejects_empty_url():
    response = TestClient(app).post("/api/audit", json={"url": ""})
    assert response.status_code == 400


def test_audit_form_rejects_bad_host():
    response = TestClient(app).post("/audit", data={"url": "not-a-host", "max_pages": "8"})
    assert response.status_code == 400
    assert "full website address" in response.text


def test_verdict_copy_for_critical_and_split_scores():
    critical = verdict_copy(_scored_sample())
    assert critical is not None
    assert "hard stop" in critical["headline"]
    assert critical["tone"] == "block"

    split = {
        "site": "example.com",
        "summary": {"total_findings": 1, "critical": 0, "high": 1, "medium": 0, "low": 0},
        "scores": {"ai_discoverability_score": 82, "engagement_score": 40, "overall_score": 63},
    }
    copy = verdict_copy(split)
    assert copy is not None
    assert copy["tone"] == "split"
    assert "visitors may stall" in copy["headline"]


def test_coverage_view_percentages():
    view = coverage_view(
        {
            "pages_discovered": 10,
            "pages_crawled": 7,
            "pages_blocked": 2,
            "pages_failed": 1,
            "pages_rendered": 0,
            "rendering_status": "skipped",
        }
    )
    assert view is not None
    assert view["pct_crawled"] == 70
    assert view["pct_blocked"] == 20
    assert view["pct_failed"] == 10


def test_audit_form_renders_report(monkeypatch):
    payload = _scored_sample()

    async def fake_audit(url: str, max_pages: int):
        assert url == "https://example.com"
        assert max_pages == 8
        return payload

    monkeypatch.setattr("brand_ai_readiness.web.perform_audit", fake_audit)
    response = TestClient(app).post("/audit", data={"url": "example.com", "max_pages": "8"})
    assert response.status_code == 200
    html = response.text
    assert "Assistants hit a hard stop on this site." in html
    assert "What we fetched" in html
    assert "What to fix" in html
    assert "Where on-page work stops helping" in html
    assert "How this was scored" in html
    assert "robots.txt blocks important pages" in html
    assert "Search crawlers cannot read important pages." in html
    assert "https://example.com/about" in html
    assert "Check site" in html
