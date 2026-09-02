from __future__ import annotations

import gzip
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from brand_ai_readiness.crawler.urls import is_http_url, normalize_url, same_origin
from brand_ai_readiness.models.snapshot import SitemapInfo

logger = logging.getLogger(__name__)

_LOC_TAGS = {"{http://www.sitemaps.org/schemas/sitemap/0.9}loc", "loc"}
_GZIP_MAGIC = b"\x1f\x8b"


def looks_like_html(text: str) -> bool:
    head = text.lstrip()[:180].lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


def looks_like_xml_sitemap(text: str) -> bool:
    head = text.lstrip()[:400].lower()
    return (
        head.startswith("<?xml")
        or "<urlset" in head
        or "<sitemapindex" in head
    )


def decode_sitemap_bytes(body: bytes, content_type: str = "") -> tuple[str | None, str | None]:
    raw = body or b""
    if raw.startswith(_GZIP_MAGIC):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            return None, f"gzip_decompress_failed:{exc}"
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if not stripped:
        return None, "empty"
    if looks_like_xml_sitemap(stripped):
        return stripped, None
    if looks_like_html(stripped) or "html" in (content_type or "").lower():
        return None, "html_not_xml"
    return stripped, None


def _is_nested_sitemap(url: str, parent_is_index: bool) -> bool:
    path = urlparse(url).path.lower()
    if parent_is_index:
        return True
    return path.endswith((".xml", ".xml.gz", ".gz")) and "sitemap" in path


def parse_sitemap_document(
    text: str,
    base_url: str,
    start_url: str,
    limit: int = 200,
) -> tuple[list[str], list[str]]:
    pages: list[str] = []
    children: list[str] = []
    if looks_like_html(text) and not looks_like_xml_sitemap(text):
        logger.info("sitemap skip for %s: html_not_xml", base_url)
        return [], []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.info("sitemap parse error for %s: %s", base_url, exc)
        return [], []

    parent_is_index = root.tag.split("}")[-1].lower() == "sitemapindex"
    for node in root.iter():
        tag = str(node.tag)
        if tag not in _LOC_TAGS and not tag.endswith("}loc"):
            continue
        loc = (node.text or "").strip()
        if not loc:
            continue
        normalized = normalize_url(loc, base_url)
        if not normalized or not is_http_url(normalized):
            continue
        if _is_nested_sitemap(normalized, parent_is_index):
            children.append(normalized)
            continue
        if same_origin(normalized, start_url):
            pages.append(normalized)
        if len(pages) >= limit:
            break
    return pages, children


def parse_sitemap_xml(body: str, base_url: str, start_url: str, limit: int = 200) -> list[str]:
    pages, _children = parse_sitemap_document(body, base_url, start_url, limit=limit)
    return pages


def default_sitemap_guesses(origin: str) -> list[str]:
    root = origin.rstrip("/") + "/"
    return [
        urljoin(root, "sitemap.xml"),
        urljoin(root, "sitemap.xml.gz"),
        urljoin(root, "sitemap_index.xml"),
        urljoin(root, "sitemap-index.xml"),
    ]


def merge_sitemap_info(
    discovered: list[str],
    urls: list[str],
    errors: list[str] | None = None,
) -> SitemapInfo:
    unique_urls = list(dict.fromkeys(urls))
    return SitemapInfo(
        discovered=list(dict.fromkeys(discovered)),
        accessible=bool(unique_urls),
        urls=unique_urls,
        errors=errors or [],
    )
