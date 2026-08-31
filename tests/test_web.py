from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from brand_ai_readiness.web import app, normalize_public_url


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
    assert "Recommend-only" not in response.text


def test_normalize_public_url():
    assert normalize_public_url("example.com") == "https://example.com"
    assert normalize_public_url("https://example.com/about") == "https://example.com/about"
    with pytest.raises(ValueError):
        normalize_public_url("not-a-host")


def test_audit_api_rejects_empty_url():
    response = TestClient(app).post("/api/audit", json={"url": ""})
    assert response.status_code == 400
