"""Choose the best HTML/text representation of a page (raw vs rendered)."""

from __future__ import annotations

from brand_ai_readiness.analysis.html import extract_links, parse_html, title_text
from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage


def effective_page(page: FetchedPage, snapshot: CrawlSnapshot) -> FetchedPage:
    """Prefer browser-rendered HTML when it contains substantially more content."""
    rendered = snapshot.desktop_rendered(page)
    if not rendered or rendered.error or not rendered.html:
        return page
    if rendered.word_count <= max(page.word_count, 0) + 10:
        return page
    soup = parse_html(rendered.html)
    internal, external = extract_links(soup, page.final_url or page.url)
    return page.model_copy(
        update={
            "html": rendered.html,
            "text": rendered.visible_text or page.text,
            "word_count": rendered.word_count,
            "heading_count": rendered.heading_count or page.heading_count,
            "internal_links": internal or page.internal_links,
            "external_links": external or page.external_links,
            "title": title_text(soup) or page.title,
        }
    )
