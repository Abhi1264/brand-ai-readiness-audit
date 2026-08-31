from __future__ import annotations

import os

import pytest

from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.orchestration.compose import run_audit

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.environ.get("LIVE_AUDIT") != "1", reason="Set LIVE_AUDIT=1 to run")
@pytest.mark.asyncio
async def test_example_com_produces_valid_report():
    report = await run_audit("https://example.com", AuditBudget(max_pages=5, max_renders=0, enable_render=False))
    assert report.site
    assert report.summary.total_findings == len(report.findings)
