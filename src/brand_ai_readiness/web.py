from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from brand_ai_readiness import __version__
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.orchestration.compose import run_audit

HOSTED_MAX_PAGES = 20
PACKAGE_DIR = Path(__file__).resolve().parent

LABELS = {
    "crawlability": "Reach",
    "rendering": "HTML vs render",
    "machine_readability": "Readable HTML",
    "structured_data": "Structured data",
    "entity": "Identity",
    "entity_clarity": "Identity",
    "freshness": "Freshness",
    "freshness_transparency": "Freshness",
    "corroboration": "Corroboration",
    "engagement": "First visit",
    "mobile": "Mobile",
    "coverage": "Coverage",
    "homepage_orientation": "Homepage orientation",
    "navigation": "Navigation",
    "cta_clarity": "Calls to action",
    "internal_linking": "Internal links",
}

ASSISTANT_KEYS = (
    "crawlability",
    "machine_readability",
    "structured_data",
    "entity_clarity",
    "freshness_transparency",
)
VISITOR_KEYS = (
    "homepage_orientation",
    "navigation",
    "cta_clarity",
    "internal_linking",
    "mobile",
)

app = FastAPI(title="AI Readiness Auditor", version=__version__)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


class AuditRequest(BaseModel):
    url: str
    max_pages: int = Field(default=12, ge=1, le=HOSTED_MAX_PAGES)


def normalize_public_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise ValueError("Enter a website address, like example.com.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = (urlparse(url).hostname or "").strip().lower()
    if not host or "." not in host:
        raise ValueError("Use a full website address, like example.com.")
    return url


def hosted_budget(max_pages: int) -> AuditBudget:
    return AuditBudget(
        max_pages=min(max(max_pages, 1), HOSTED_MAX_PAGES),
        max_renders=0,
        enable_render=False,
        request_timeout_s=12.0,
        max_concurrency=4,
    )


async def perform_audit(url: str, max_pages: int) -> dict[str, Any]:
    report = await run_audit(url, hosted_budget(max_pages))
    return report.model_dump_public()


async def audited_payload(url: str, max_pages: int) -> dict[str, Any]:
    try:
        target = normalize_public_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await perform_audit(target, max_pages)


def checked_label(iso: str | None) -> str:
    if not iso:
        return "just now"
    try:
        stamp = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return iso
    return f"{stamp:%b} {stamp.day}, {stamp.year}"


def category_label(slug: str | None) -> str:
    if not slug:
        return ""
    return LABELS.get(slug, slug.replace("_", " "))


def _count(data: dict[str, Any], key: str) -> int:
    return int(data.get(key) or 0)


def verdict_copy(report: dict[str, Any] | None) -> dict[str, str] | None:
    if not report:
        return None
    scores = report.get("scores") or {}
    disco = scores.get("ai_discoverability_score")
    eng = scores.get("engagement_score")
    overall = scores.get("overall_score")
    summary = report.get("summary") or {}
    critical = _count(summary, "critical")
    high = _count(summary, "high")
    total = _count(summary, "total_findings")
    site = report.get("site") or "This site"

    if disco is None or eng is None:
        return {
            "headline": f"{site} was checked.",
            "detail": "Scores were not produced for this scan.",
            "tone": "mixed",
        }
    if critical:
        noun = "issue" if critical == 1 else "issues"
        return {
            "headline": "Assistants hit a hard stop on this site.",
            "detail": (
                f"{critical} critical {noun} would block crawling or citation "
                "before anything else is worth fixing."
            ),
            "tone": "block",
        }
    if disco >= 75 and eng >= 75:
        return {
            "headline": "Assistants and visitors can both make sense of this site.",
            "detail": "The mechanical basics are healthy. Remaining items are polish on the pages we crawled.",
            "tone": "ok",
        }
    if disco >= 70 and eng < 55:
        return {
            "headline": "Assistants can find this site; visitors may stall.",
            "detail": "The pages are reachable, but the first visit does not explain who it is for or what to do next.",
            "tone": "split",
        }
    if eng >= 70 and disco < 55:
        return {
            "headline": "Visitors can find their way; assistants may not.",
            "detail": "Humans can orient, but machines lack the structure or access they need to cite this brand.",
            "tone": "split",
        }
    if total == 0:
        return {
            "headline": "No issues on the pages we scanned.",
            "detail": "A strong starting point for the crawled set — not a claim about the rest of the site.",
            "tone": "ok",
        }
    if high and (overall is None or overall < 70):
        noun = "issue" if high == 1 else "issues"
        return {
            "headline": "This site is only partly usable as a source.",
            "detail": f"{high} high-severity {noun} on the crawled pages are the fastest way to raise the score.",
            "tone": "mixed",
        }
    return {
        "headline": "Readable in places, unclear in others.",
        "detail": "Fix the items below in severity order. Each one is tied to pages we actually fetched.",
        "tone": "mixed",
    }


def coverage_view(coverage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not coverage:
        return None
    crawled = _count(coverage, "pages_crawled")
    failed = _count(coverage, "pages_failed")
    blocked = _count(coverage, "pages_blocked")
    discovered = _count(coverage, "pages_discovered")
    total = max(discovered, crawled + failed + blocked, 1)

    def pct(count: int) -> float:
        return round(100 * count / total, 2)

    leftover = max(0, total - crawled - blocked - failed)
    return {
        "crawled": crawled,
        "failed": failed,
        "blocked": blocked,
        "discovered": discovered,
        "rendering_status": coverage.get("rendering_status") or "skipped",
        "access_probe_status": coverage.get("access_probe_status") or "",
        "limitations": coverage.get("limitations") or [],
        "pct_crawled": pct(crawled),
        "pct_blocked": pct(blocked),
        "pct_failed": pct(failed),
        "pct_rest": pct(leftover),
    }


def component_groups(scores: dict[str, Any] | None) -> list[dict[str, Any]]:
    components = (scores or {}).get("components") or {}
    if not components:
        return []
    groups: list[dict[str, Any]] = []
    for title, keys in (("For assistants", ASSISTANT_KEYS), ("For visitors", VISITOR_KEYS)):
        items = [
            {"key": key, "label": category_label(key), "value": int(components[key])}
            for key in keys
            if key in components
        ]
        if items:
            groups.append({"title": title, "items": items})
    return groups


def finding_categories(findings: list[Any] | None) -> list[str]:
    seen: list[str] = []
    for item in findings or []:
        category = item.get("category")
        if category and category not in seen:
            seen.append(category)
    return seen


templates.env.filters["category_label"] = category_label
templates.env.filters["site_type_label"] = category_label


def render_page(
    request: Request,
    *,
    url: str = "",
    error: str | None = None,
    report: dict[str, Any] | None = None,
    max_pages: int = 12,
    status_code: int = 200,
) -> HTMLResponse:
    scores = (report or {}).get("scores")
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "url": url,
            "error": error,
            "report": report,
            "max_pages": max_pages,
            "max_pages_cap": HOSTED_MAX_PAGES,
            "checked_label": checked_label((report or {}).get("audited_at")),
            "verdict": verdict_copy(report),
            "coverage": coverage_view((report or {}).get("coverage")),
            "component_groups": component_groups(scores),
            "finding_categories": finding_categories((report or {}).get("findings")),
        },
        status_code=status_code,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, url: str = "") -> HTMLResponse:
    return render_page(request, url=url)


@app.get("/api/audit")
async def audit_get(url: str, max_pages: int = 12) -> dict[str, Any]:
    return await audited_payload(url, max_pages)


@app.post("/api/audit")
async def audit_post(payload: AuditRequest) -> dict[str, Any]:
    return await audited_payload(payload.url, payload.max_pages)


@app.post("/audit")
async def audit_form(
    request: Request,
    url: str = Form(...),
    max_pages: int = Form(12),
):
    if "application/json" in (request.headers.get("accept") or ""):
        return await audited_payload(url, max_pages)
    try:
        target = normalize_public_url(url)
    except ValueError as exc:
        return render_page(request, error=str(exc), url=url, max_pages=max_pages, status_code=400)
    payload = await perform_audit(target, max_pages)
    return render_page(request, url=target, report=payload, max_pages=max_pages)
