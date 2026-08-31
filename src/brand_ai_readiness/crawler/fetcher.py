"""Read-only HTTP fetch with size, timeout, retry, and method guards."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from brand_ai_readiness.config import SAFE_METHODS, AuditBudget

logger = logging.getLogger(__name__)


class UnsafeMethodError(RuntimeError):
    """Raised if anything tries a non-GET/HEAD request."""


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    headers: dict[str, str]
    redirect_chain: list[str]
    error: str | None = None
    retry_count: int = 0


def _guard_method(method: str) -> None:
    if method.upper() not in SAFE_METHODS:
        raise UnsafeMethodError(f"refusing non-read method {method}")


async def fetch_bytes(
    client: httpx.AsyncClient,
    url: str,
    budget: AuditBudget,
    method: str = "GET",
) -> FetchResult:
    _guard_method(method)
    last_error: str | None = None
    retries = 0
    for attempt in range(budget.max_retries + 1):
        try:
            response = await client.request(
                method,
                url,
                follow_redirects=True,
                timeout=budget.request_timeout_s,
            )
            content_type = response.headers.get("content-type", "")
            body = response.content[: budget.max_response_bytes]
            chain = [str(item.url) for item in response.history] + [str(response.url)]
            if len(chain) > budget.max_redirects + 1:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    body=b"",
                    headers={k.lower(): v for k, v in response.headers.items()},
                    redirect_chain=chain,
                    error="excessive_redirects",
                    retry_count=retries,
                )
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                body=body,
                headers={k.lower(): v for k, v in response.headers.items()},
                redirect_chain=chain,
                retry_count=retries,
            )
        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.TooManyRedirects:
            last_error = "redirect_loop"
        except httpx.HTTPError as exc:
            last_error = f"http_error:{exc.__class__.__name__}"
        retries = attempt + 1
        if attempt < budget.max_retries:
            logger.debug("retry %s for %s after %s", retries, url, last_error)
    return FetchResult(
        url=url,
        final_url=url,
        status_code=0,
        content_type="",
        body=b"",
        headers={},
        redirect_chain=[],
        error=last_error or "unknown",
        retry_count=retries,
    )


def decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    if "charset=" in content_type.lower():
        charset = content_type.lower().split("charset=", 1)[1].split(";")[0].strip()
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
