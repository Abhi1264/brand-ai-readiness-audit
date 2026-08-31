from __future__ import annotations

import pytest

from brand_ai_readiness.analysis.html import visible_text, word_count
from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.rendering.renderer import render_pages_async, render_snapshot_pages_async
from brand_ai_readiness.models.snapshot import FetchedPage, RenderedPage
from brand_ai_readiness.rendering.compare import compare_raw_and_rendered
from tests.helpers import load_site_html, page_from_html


def test_static_page_is_not_a_render_gap():
    html = load_site_html("01_excellent", "index.html")
    page = page_from_html("https://fixture.test/", html, role="homepage")
    rendered = RenderedPage(
        url=page.url,
        html=html,
        visible_text=page.text,
        viewport="desktop",
        word_count=page.word_count,
    )
    gap = compare_raw_and_rendered(page, rendered)
    assert gap.meaningful is False


def test_js_generated_content_is_meaningful_gap():
    raw = load_site_html("03_js_only", "index.html")
    rendered_html = load_site_html("03_js_only", "rendered.html")
    page = page_from_html("https://fixture.test/", raw, role="homepage")
    rendered = RenderedPage(
        url=page.url,
        html=rendered_html,
        visible_text=visible_text(rendered_html),
        viewport="desktop",
        word_count=word_count(visible_text(rendered_html)),
    )
    gap = compare_raw_and_rendered(page, rendered)
    assert gap.raw_words < 30
    assert gap.rendered_words > 20
    assert gap.meaningful is True
    assert "pricing" in gap.facts_only_in_render or "body copy / descriptions" in gap.facts_only_in_render


def test_javascript_presence_alone_is_not_a_gap():
    html = "<html><body><h1>Hello</h1><p>Visible copy that is enough.</p><script>console.log(1)</script></body></html>"
    page = FetchedPage(
        url="https://fixture.test/",
        final_url="https://fixture.test/",
        html=html,
        text=visible_text(html),
        word_count=word_count(visible_text(html)),
        role="homepage",
    )
    rendered = RenderedPage(url=page.url, html=html, visible_text=page.text, word_count=page.word_count)
    assert compare_raw_and_rendered(page, rendered).meaningful is False


@pytest.mark.asyncio
async def test_async_render_inside_running_loop_does_not_crash():
    page = page_from_html(
        "https://fixture.test/",
        "<html><body><h1>Hi</h1></body></html>",
        role="homepage",
    )
    rendered, status = await render_pages_async([page], AuditBudget(enable_render=False))
    assert rendered == []
    assert status == "skipped"


@pytest.mark.asyncio
async def test_async_render_disabled_snapshot():
    from tests.helpers import snapshot_from_site_dir

    snapshot = snapshot_from_site_dir("01_excellent")
    await render_snapshot_pages_async(snapshot, AuditBudget(enable_render=False))
    assert snapshot.stats.rendering_status == "skipped"
