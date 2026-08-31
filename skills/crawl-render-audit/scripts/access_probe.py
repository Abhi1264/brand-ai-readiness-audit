#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

import httpx  # noqa: E402

from brand_ai_readiness.config import AuditBudget  # noqa: E402
from brand_ai_readiness.crawler.access_probe import probe_access  # noqa: E402
from brand_ai_readiness.crawler.robots import empty_robots, parse_robots  # noqa: E402
from brand_ai_readiness.crawler.urls import origin_of  # noqa: E402


async def _run(url: str, timeout: float) -> list[dict]:
    budget = AuditBudget(request_timeout_s=timeout)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        policy = empty_robots(url)
        try:
            resp = await client.get(f"{origin_of(url)}/robots.txt", timeout=timeout)
            if resp.status_code == 200 and resp.text:
                policy = parse_robots(resp.text, f"{origin_of(url)}/robots.txt")
        except httpx.HTTPError:
            pass
        probes = await probe_access(client, url, budget, policy)
    return [probe.model_dump(mode="json") for probe in probes]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare what an origin serves a browser vs named AI crawlers (read-only)."
    )
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    url = args.url if args.url.startswith(("http://", "https://")) else "https://" + args.url
    print(json.dumps(asyncio.run(_run(url, args.timeout)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
