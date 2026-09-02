from __future__ import annotations

import re
from typing import Any

from brand_ai_readiness.analysis.html import json_ld_blocks, meta_content, open_graph, parse_html, prices_in_text
from brand_ai_readiness.models.snapshot import CrawlSnapshot, FetchedPage, StructuredBlock

_JSONLD_KEEP = {
    "name",
    "description",
    "url",
    "sku",
    "price",
    "priceCurrency",
    "brand",
    "sameAs",
    "datePublished",
    "dateModified",
    "offers",
}


def _walk_jsonld(node: Any, acc: list[dict[str, Any]]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, acc)
        return
    if isinstance(node, dict):
        if "@graph" in node:
            _walk_jsonld(node["@graph"], acc)
        acc.append(node)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk_jsonld(value, acc)


def flatten_jsonld(parsed: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    acc: list[dict[str, Any]] = []
    _walk_jsonld(parsed, acc)
    return acc


def schema_types(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if raw:
        return [str(raw)]
    return []


def _blocks_from_html(url: str, html: str) -> list[StructuredBlock]:
    blocks: list[StructuredBlock] = []
    soup = parse_html(html)
    for parsed, error in json_ld_blocks(soup):
        if error or parsed is None:
            blocks.append(StructuredBlock(url=url, kind="jsonld", parse_error=error or "empty"))
            continue
        for node in flatten_jsonld(parsed):
            blocks.append(
                StructuredBlock(
                    url=url,
                    kind="jsonld",
                    types=schema_types(node),
                    data={
                        key: value
                        for key, value in node.items()
                        if key in _JSONLD_KEEP or not isinstance(value, (dict, list))
                    },
                )
            )
    og = open_graph(soup)
    if og:
        blocks.append(
            StructuredBlock(
                url=url,
                kind="opengraph",
                types=[og.get("og:type", "website")],
                data=dict(og),
            )
        )
    desc = meta_content(soup, "description")
    if desc:
        blocks.append(StructuredBlock(url=url, kind="meta", types=["description"], data={"description": desc}))
    return blocks


def collect_structured(snapshot: CrawlSnapshot) -> CrawlSnapshot:
    blocks: list[StructuredBlock] = []
    seen_html: set[tuple[str, str]] = set()
    for page in snapshot.successful_pages():
        key = (page.url, page.html[:80] if page.html else "")
        if key not in seen_html:
            seen_html.add(key)
            blocks.extend(_blocks_from_html(page.url, page.html))
        rendered = snapshot.desktop_rendered(page)
        if rendered and rendered.html and rendered.html != page.html:
            blocks.extend(_blocks_from_html(page.url, rendered.html))
    snapshot.structured = blocks
    return snapshot


def jsonld_types_by_url(snapshot: CrawlSnapshot) -> dict[str, set[str]]:
    by_url: dict[str, set[str]] = {}
    for block in snapshot.structured:
        if block.kind != "jsonld":
            continue
        by_url.setdefault(block.url, set()).update(block.types)
    return by_url


def jsonld_types_on(snapshot: CrawlSnapshot, url: str | None = None) -> set[str]:
    by_url = jsonld_types_by_url(snapshot)
    if url:
        return set(by_url.get(url, ()))
    types: set[str] = set()
    for group in by_url.values():
        types.update(group)
    return types


def jsonld_dates_by_url(snapshot: CrawlSnapshot) -> dict[str, dict[str, str]]:
    by_url: dict[str, dict[str, str]] = {}
    for block in snapshot.structured:
        if block.kind != "jsonld":
            continue
        dates = by_url.setdefault(block.url, {})
        for key in ("datePublished", "dateModified"):
            value = block.data.get(key)
            if isinstance(value, str):
                dates[key] = value
    return by_url


def malformed_jsonld_pages(snapshot: CrawlSnapshot) -> list[str]:
    return [block.url for block in snapshot.structured if block.kind == "jsonld" and block.parse_error]


def name_mismatches(page: FetchedPage, snapshot: CrawlSnapshot) -> list[tuple[str, str]]:
    mismatches: list[tuple[str, str]] = []
    visible = (page.text or "").lower()
    title = (page.title or "").lower()
    for block in snapshot.structured:
        if block.url != page.url or block.kind != "jsonld":
            continue
        name = block.data.get("name")
        if not isinstance(name, str) or len(name) < 3:
            continue
        token = name.strip().lower()
        if token in visible or token in title:
            continue
        parts = [part for part in token.split() if len(part) > 2]
        if parts and sum(part in visible or part in title for part in parts) / len(parts) >= 0.6:
            continue
        title_lead = title.split("|")[0].strip()
        if title_lead and title_lead not in token:
            mismatches.append((name, page.title or visible[:80]))
    return mismatches


def _digits_price(value: str) -> str:
    return re.sub(r"[^\d.]", "", value)


def price_mismatches(page: FetchedPage, snapshot: CrawlSnapshot) -> list[tuple[str, list[str]]]:
    visible_prices = set(prices_in_text(page.text))
    visible_norm = {_digits_price(item) for item in visible_prices}
    mismatches: list[tuple[str, list[str]]] = []
    for block in snapshot.structured:
        if block.url != page.url:
            continue
        price = block.data.get("price")
        if price is None:
            offers = block.data.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
        if price is None:
            continue
        structured_price = str(price)
        structured_norm = _digits_price(structured_price)
        if visible_norm and structured_norm and structured_norm not in visible_norm:
            mismatches.append((structured_price, sorted(visible_prices)))
    return mismatches
