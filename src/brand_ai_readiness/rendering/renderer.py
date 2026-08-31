from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Literal, TypeVar

from brand_ai_readiness.analysis.html import json_ld_blocks, parse_html, visible_text, word_count
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage, RenderedPage
from brand_ai_readiness.rendering.select import select_representative_pages

logger = logging.getLogger(__name__)

_EVAL_SCRIPT = """
() => {
  const text = document.body ? document.body.innerText : "";
  const overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 8;
  const nav = document.querySelector("nav, [role='navigation'], header");
  const cta = Array.from(document.querySelectorAll("a, button")).some((el) => {
    const t = (el.innerText || "").toLowerCase();
    return /get started|sign up|contact|demo|buy|pricing|subscribe|book/.test(t);
  });
  let minFont = 16;
  document.querySelectorAll("p, h1, h2, a, button, li").forEach((el) => {
    const size = parseFloat(getComputedStyle(el).fontSize || "16");
    if (!Number.isNaN(size)) minFont = Math.min(minFont, size);
  });
  return {
    text,
    overflow,
    navVisible: !!(nav && nav.offsetParent !== null),
    ctaVisible: cta,
    minFont,
    headingCount: document.querySelectorAll("h1,h2,h3").length,
    linkCount: document.querySelectorAll("a[href]").length,
  };
}
"""


RenderingStatus = Literal["complete", "partial", "unavailable", "skipped"]
_T = TypeVar("_T")


def _page_from_metrics(url: str, html: str, metrics: dict[str, Any], label: str) -> RenderedPage:
    text = metrics.get("text") or visible_text(html)
    jsonld = len([block for block, err in json_ld_blocks(parse_html(html)) if err is None])
    return RenderedPage(
        url=url,
        html=html,
        visible_text=text,
        viewport=label,
        word_count=word_count(text),
        heading_count=int(metrics.get("headingCount") or 0),
        link_count=int(metrics.get("linkCount") or 0),
        jsonld_count=jsonld,
        overflow_x=bool(metrics.get("overflow")),
        nav_visible=bool(metrics.get("navVisible")),
        cta_visible=bool(metrics.get("ctaVisible")),
        min_font_px=float(metrics.get("minFont") or 0) or None,
    )


async def _render_one_async(
    page_obj: Any, url: str, viewport: tuple[int, int], timeout_ms: int, label: str
) -> RenderedPage:
    await page_obj.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    await page_obj.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    await page_obj.wait_for_timeout(600)
    html = await page_obj.content()
    metrics = await page_obj.evaluate(_EVAL_SCRIPT)
    return _page_from_metrics(url, html, metrics, label)


def _status_from(rendered: list[RenderedPage]) -> RenderingStatus:
    if not rendered:
        return "unavailable"
    errors = [item for item in rendered if item.error]
    if errors and len(errors) == len(rendered):
        return "unavailable"
    if errors:
        return "partial"
    return "complete"


async def render_pages_async(
    pages: list[FetchedPage],
    budget: AuditBudget,
) -> tuple[list[RenderedPage], RenderingStatus]:
    if not budget.enable_render:
        return [], "skipped"
    if not pages:
        return [], "skipped"
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # noqa: BLE001
        logger.info("Playwright import unavailable: %s", exc)
        return [], "unavailable"

    rendered: list[RenderedPage] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=budget.user_agent)
            page_obj = await context.new_page()
            timeout_ms = int(budget.render_timeout_s * 1000)
            for fetched in pages:
                target = fetched.final_url or fetched.url
                try:
                    rendered.append(
                        await _render_one_async(
                            page_obj, target, budget.desktop_viewport, timeout_ms, "desktop"
                        )
                    )
                    rendered.append(
                        await _render_one_async(
                            page_obj, target, budget.mobile_viewport, timeout_ms, "mobile"
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.info("render failed for %s: %s", fetched.url, exc)
                    rendered.append(RenderedPage(url=fetched.url, viewport="desktop", error=str(exc)))
            await browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.info("Playwright launch unavailable: %s", exc)
        return rendered, "unavailable" if not rendered else "partial"
    return rendered, _status_from(rendered)


def _run_sync(coro: Coroutine[Any, Any, _T], sync_name: str, async_name: str) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError(f"{sync_name}() is sync; use {async_name}() inside an event loop")


def render_pages(
    pages: list[FetchedPage],
    budget: AuditBudget,
) -> tuple[list[RenderedPage], RenderingStatus]:
    return _run_sync(render_pages_async(pages, budget), "render_pages", "render_pages_async")


async def render_snapshot_pages_async(snapshot: CrawlSnapshot, budget: AuditBudget) -> CrawlSnapshot:
    selected = select_representative_pages(snapshot, budget.max_renders)
    rendered, status = await render_pages_async(selected, budget)
    snapshot.rendered = rendered
    snapshot.stats.pages_rendered = len({item.url for item in rendered if not item.error})
    snapshot.stats.rendering_status = status
    return snapshot


def render_snapshot_pages(snapshot: CrawlSnapshot, budget: AuditBudget) -> CrawlSnapshot:
    return _run_sync(
        render_snapshot_pages_async(snapshot, budget),
        "render_snapshot_pages",
        "render_snapshot_pages_async",
    )
