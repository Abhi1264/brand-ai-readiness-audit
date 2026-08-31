"""URL normalization, origin checks, and host extraction."""

from __future__ import annotations

from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

from brand_ai_readiness.config import TRACKING_QUERY_PARAMS


def strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def drop_tracking_params(url: str) -> str:
    parsed = urlparse(url)
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = "&".join(f"{key}={value}" if value != "" else key for key, value in kept)
    return urlunparse(parsed._replace(query=query))


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    collapsed = "/".join(part for part in path.split("/") if part not in {".", ""})
    if path.startswith("/"):
        collapsed = "/" + collapsed
    if path.endswith("/") and collapsed != "/":
        collapsed += "/"
    # Treat /about and /about/ as the same page for crawl de-dupe.
    if collapsed != "/" and collapsed.endswith("/"):
        collapsed = collapsed[:-1]
    return collapsed or "/"


def normalize_url(url: str, base: str | None = None) -> str:
    """Canonicalize a URL for crawl de-duplication."""
    raw = url.strip()
    if base:
        raw = urljoin(base, raw)
    raw = strip_fragment(raw)
    raw = drop_tracking_params(raw)
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    if scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    port = parsed.port
    netloc = host
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = _normalize_path(parsed.path)
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def same_origin(left: str, right: str) -> bool:
    return origin_of(left) == origin_of(right)


def site_label(url: str) -> str:
    """Host used as the report `site` field."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    return host.removeprefix("www.") or host


def is_probably_asset(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(
        (
            ".css",
            ".js",
            ".mjs",
            ".map",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".mp4",
            ".webm",
            ".mp3",
            ".zip",
            ".gz",
            ".pdf",
        )
    )


def is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}
