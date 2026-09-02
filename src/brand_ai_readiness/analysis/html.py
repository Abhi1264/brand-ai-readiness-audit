from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, Tag

from brand_ai_readiness.crawler.urls import is_http_url, is_probably_asset, normalize_url, same_origin

_WS = re.compile(r"\s+")
_WORD = re.compile(r"\b\w+\b")
_PRICE = re.compile(r"(?:USD|INR|EUR|GBP|\$|€|£|₹)\s?\d[\d,]*(?:\.\d{2})?", re.I)
_CTA_WORDS = re.compile(
    r"\b(get started|start free|start now|sign up|signup|try free|book (a )?demo|"
    r"contact (us|sales)|request (a )?demo|buy now|shop now|add to cart|subscribe|"
    r"learn more|see pricing|view pricing|talk to|schedule)\b",
    re.I,
)


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "lxml")


def visible_text(soup: BeautifulSoup | str) -> str:
    if isinstance(soup, str):
        soup = parse_html(soup)
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda item: isinstance(item, Comment)):
        comment.extract()
    text = soup.get_text(" ", strip=True)
    return _WS.sub(" ", text)


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def headings(soup: BeautifulSoup) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for level in range(1, 7):
        for node in soup.find_all(f"h{level}"):
            text = node.get_text(" ", strip=True)
            if text:
                found.append({"level": f"h{level}", "text": text[:240]})
    return found


def title_text(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def canonical_href(soup: BeautifulSoup, page_url: str) -> str | None:
    link = soup.find("link", rel=lambda value: value and "canonical" in value)
    if not isinstance(link, Tag):
        return None
    href = link.get("href")
    if not href:
        return None
    return normalize_url(str(href), page_url) or None


def robots_meta(soup: BeautifulSoup) -> str | None:
    node = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if not isinstance(node, Tag):
        return None
    content = node.get("content")
    return str(content).strip() if content else None


def has_noindex(meta: str | None) -> bool:
    if not meta:
        return False
    return "noindex" in meta.lower()


def extract_links(soup: BeautifulSoup, page_url: str) -> tuple[list[str], list[str]]:
    internal: list[str] = []
    external: list[str] = []
    seen: set[str] = set()
    for node in soup.find_all("a", href=True):
        href = str(node.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = normalize_url(urljoin(page_url, href), page_url)
        if not absolute or not is_http_url(absolute) or is_probably_asset(absolute):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        if same_origin(absolute, page_url):
            internal.append(absolute)
        else:
            external.append(absolute)
    return internal, external


@lru_cache(maxsize=64)
def _meta_name_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(name)}$", re.I)


def meta_content(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        pattern = _meta_name_pattern(name)
        for attr in ("name", "property"):
            node = soup.find("meta", attrs={attr: pattern})
            if isinstance(node, Tag) and node.get("content"):
                return str(node.get("content")).strip()
    return None


def open_graph(soup: BeautifulSoup) -> dict[str, str]:
    data: dict[str, str] = {}
    for node in soup.find_all("meta"):
        if not isinstance(node, Tag):
            continue
        prop = node.get("property") or node.get("name")
        content = node.get("content")
        if prop and content and str(prop).lower().startswith("og:"):
            data[str(prop).lower()] = str(content).strip()
    return data


def json_ld_blocks(soup: BeautifulSoup) -> list[tuple[dict[str, Any] | list[Any] | None, str | None]]:
    blocks: list[tuple[dict[str, Any] | list[Any] | None, str | None]] = []
    for node in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = node.string or node.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            blocks.append((json.loads(raw), None))
        except json.JSONDecodeError as exc:
            blocks.append((None, str(exc)))
    return blocks


def jsonld_ok_count(soup: BeautifulSoup) -> int:
    return sum(error is None for _parsed, error in json_ld_blocks(soup))


def prices_in_text(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in _PRICE.finditer(text or "")))


def cta_matches(text: str) -> list[str]:
    return [match.group(0) for match in _CTA_WORDS.finditer(text or "")]


def image_alts(soup: BeautifulSoup) -> list[str]:
    alts: list[str] = []
    for node in soup.find_all("img"):
        alt = node.get("alt")
        if alt:
            alts.append(str(alt).strip())
    return alts


def has_canvas_or_embed(soup: BeautifulSoup) -> dict[str, int]:
    counts = {"canvas": 0, "iframe": 0, "embed": 0, "svg": 0, "img": 0}
    for tag in soup.find_all(["canvas", "iframe", "embed", "object", "svg", "img"]):
        name = tag.name
        if name == "object":
            counts["embed"] += 1
        elif name in counts:
            counts[name] += 1
    return counts
