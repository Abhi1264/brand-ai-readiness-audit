from __future__ import annotations

from dataclasses import dataclass

from brand_ai_readiness.analysis.html import (
    cta_matches,
    headings,
    json_ld_blocks,
    parse_html,
    prices_in_text,
    visible_text,
    word_count,
)
from brand_ai_readiness.models.snapshot import FetchedPage, RenderedPage


@dataclass
class RenderGap:
    url: str
    raw_words: int
    rendered_words: int
    raw_headings: int
    rendered_headings: int
    raw_prices: list[str]
    rendered_prices: list[str]
    raw_ctas: list[str]
    rendered_ctas: list[str]
    raw_jsonld: int
    rendered_jsonld: int
    facts_only_in_render: list[str]
    ratio: float
    meaningful: bool


def compare_raw_and_rendered(page: FetchedPage, rendered: RenderedPage) -> RenderGap:
    raw_soup = parse_html(page.html)
    rendered_soup = parse_html(rendered.html) if rendered.html else None
    raw_text = page.text or visible_text(raw_soup)
    rendered_text = rendered.visible_text or (visible_text(rendered_soup) if rendered_soup else "")
    raw_words = word_count(raw_text)
    rendered_words = word_count(rendered_text)
    raw_prices = prices_in_text(raw_text)
    rendered_prices = prices_in_text(rendered_text)
    raw_ctas = cta_matches(raw_text)
    rendered_ctas = cta_matches(rendered_text)
    raw_jsonld = len([block for block, err in json_ld_blocks(raw_soup) if err is None])
    if rendered.jsonld_count:
        rendered_jsonld = rendered.jsonld_count
    elif rendered_soup is not None:
        rendered_jsonld = len([block for block, err in json_ld_blocks(rendered_soup) if err is None])
    else:
        rendered_jsonld = 0
    raw_heads = [item["text"] for item in headings(raw_soup)]
    rendered_heads = [item["text"] for item in headings(rendered_soup)] if rendered_soup else []

    facts: list[str] = []
    if rendered_prices and not raw_prices:
        facts.append("pricing")
    if rendered_heads and not raw_heads:
        facts.append("headings / product or service names")
    extra_heads = [h for h in rendered_heads if h.lower() not in {x.lower() for x in raw_heads}]
    if extra_heads and raw_words < 80:
        facts.append("primary titles")
    if rendered_ctas and not raw_ctas:
        facts.append("call-to-action text")
    if rendered_jsonld > raw_jsonld:
        facts.append("structured data")
    if rendered_words >= max(120, raw_words * 2) and raw_words < 200:
        if "product description" not in facts and rendered_words - raw_words > 80:
            facts.append("body copy / descriptions")

    ratio = (rendered_words / raw_words) if raw_words else (float("inf") if rendered_words else 1.0)
    meaningful = bool(facts) and (
        ratio >= 2.0 or (raw_words < 40 and rendered_words >= 80) or bool(rendered_prices and not raw_prices)
    )
    return RenderGap(
        url=page.url,
        raw_words=raw_words,
        rendered_words=rendered_words,
        raw_headings=len(raw_heads),
        rendered_headings=len(rendered_heads),
        raw_prices=raw_prices,
        rendered_prices=rendered_prices,
        raw_ctas=raw_ctas,
        rendered_ctas=rendered_ctas,
        raw_jsonld=raw_jsonld,
        rendered_jsonld=rendered_jsonld,
        facts_only_in_render=facts,
        ratio=ratio if ratio != float("inf") else 99.0,
        meaningful=meaningful,
    )
