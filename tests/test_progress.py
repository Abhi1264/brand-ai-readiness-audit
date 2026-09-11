from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from brand_ai_readiness.orchestration.progress import (
    Progress,
    TerminalProgress,
    make_progress,
    summarise,
)

ROOT = Path(__file__).resolve().parents[1]

REPORT = {
    "site": "example.com",
    "site_type": "saas",
    "summary": {"total_findings": 3, "critical": 1, "high": 1, "medium": 1, "low": 0},
    "findings": [
        {
            "title": "A critical thing",
            "severity": "critical",
            "suggested_action": {"summary": "Fix it first."},
        }
    ],
    "coverage": {"pages_crawled": 12, "limitations": ["Rendering was skipped."]},
    "scores": {"ai_discoverability_score": 70, "engagement_score": 60, "overall_score": 65},
}


def _plain(**kw) -> tuple[TerminalProgress, io.StringIO]:
    buf = io.StringIO()
    return TerminalProgress(stream=buf, site="example.com", **kw), buf


def test_base_progress_accepts_every_call():
    p = Progress()
    p.phase("crawl", "x")
    p.detail("crawl", "x")
    p.skip("render", "x")
    p.tick(3, 4)
    p.failed("boom")
    p.done(REPORT)


def test_make_progress_returns_a_noop_when_disabled():
    assert type(make_progress(False, "example.com")) is Progress


def test_no_ansi_escapes_when_not_a_terminal():
    reporter, buf = _plain()
    reporter.phase("robots")
    reporter.phase("crawl")
    reporter.tick(5, 2)
    reporter.skip("render", "unavailable")
    reporter.done(REPORT)
    assert "\033" not in buf.getvalue()


def test_no_ansi_escapes_when_no_color_is_set(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    reporter, buf = _plain()
    reporter.phase("crawl")
    reporter.done(REPORT)
    assert "\033" not in buf.getvalue()


def test_skip_reason_is_not_doubled():
    reporter, buf = _plain()
    reporter.skip("render", "skipped")
    assert "skipped (skipped)" not in buf.getvalue()


def test_a_closed_stream_does_not_raise():
    buf = io.StringIO()
    reporter = TerminalProgress(stream=buf, site="example.com")
    buf.close()
    reporter.phase("crawl")
    reporter.done(REPORT)


def test_summary_shows_counts_scores_and_first_fix():
    text = summarise(REPORT, elapsed=1.5)
    for expected in ("example.com", "CRITICAL 1", "HIGH 1", "MEDIUM 1",
                     "A critical thing", "Fix it first.", "overall 65", "1.5s"):
        assert expected in text, f"missing from summary: {expected!r}"


def test_summary_says_so_when_there_are_no_findings():
    empty = {**REPORT, "findings": [], "summary": {k: 0 for k in REPORT["summary"]}}
    assert "no defects found" in summarise(empty)


def test_progress_never_contaminates_stdout():
    fixture = ROOT / "tests" / "fixtures" / "sites" / "01_excellent"
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8891", "--directory", str(fixture)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        import time

        time.sleep(1.5)
        proc = subprocess.run(
            [sys.executable, "-m", "brand_ai_readiness", "http://127.0.0.1:8891/",
             "--no-render", "--max-pages", "3"],
            capture_output=True, text=True, cwd=ROOT, timeout=120,
        )
        payload = json.loads(proc.stdout)  # raises if progress leaked into stdout
        assert payload["site"]
        assert "auditing" in proc.stderr
    finally:
        server.terminate()
        server.wait(timeout=10)
