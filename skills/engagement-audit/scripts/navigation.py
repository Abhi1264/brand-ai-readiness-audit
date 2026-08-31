#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.engagement import nav_quality  # noqa: E402
from brand_ai_readiness.analysis.html import visible_text  # noqa: E402
from brand_ai_readiness.models.snapshot import FetchedPage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Navigation label quality")
    parser.add_argument("html_file")
    parser.add_argument("--url", default="https://example.com/")
    args = parser.parse_args(argv)
    html = Path(args.html_file).read_text(encoding="utf-8")
    page = FetchedPage(url=args.url, final_url=args.url, html=html, text=visible_text(html), role="homepage")
    count, confusing = nav_quality(page)
    print(json.dumps({"nav_count": count, "confusing_labels": confusing}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
