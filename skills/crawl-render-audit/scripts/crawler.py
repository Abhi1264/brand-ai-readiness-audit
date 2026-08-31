#!/usr/bin/env python3
"""Run the bounded crawler and print snapshot JSON (no findings)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.config import AuditBudget  # noqa: E402
from brand_ai_readiness.crawler.crawler import crawl_site_sync  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded same-origin crawler")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    snapshot = crawl_site_sync(args.url, AuditBudget(max_pages=args.max_pages, enable_render=False))
    payload = snapshot.model_dump(mode="json")
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
