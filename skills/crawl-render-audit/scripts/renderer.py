#!/usr/bin/env python3
"""Render selected pages with Playwright if available."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.config import AuditBudget  # noqa: E402
from brand_ai_readiness.crawler.crawler import crawl_site_sync  # noqa: E402
from brand_ai_readiness.rendering.renderer import render_snapshot_pages  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Selective Playwright renderer")
    parser.add_argument("url")
    parser.add_argument("--max-renders", type=int, default=8)
    args = parser.parse_args(argv)
    snapshot = crawl_site_sync(args.url, AuditBudget(max_pages=20, enable_render=False))
    render_snapshot_pages(snapshot, AuditBudget(max_renders=args.max_renders))
    print(
        json.dumps(
            {
                "rendering_status": snapshot.stats.rendering_status,
                "pages_rendered": snapshot.stats.pages_rendered,
                "urls": [item.url for item in snapshot.rendered if not item.error],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
