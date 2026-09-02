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


def render_page(
    request: Request,
    *,
    url: str = "",
    error: str | None = None,
    report: dict[str, Any] | None = None,
    max_pages: int = 12,
    status_code: int = 200,
) -> HTMLResponse:
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
