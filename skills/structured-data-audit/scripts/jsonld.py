#!/usr/bin/env python3
"""Parse JSON-LD blocks from an HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import skills._bootstrap  # noqa: E402, F401

from brand_ai_readiness.analysis.html import json_ld_blocks, parse_html  # noqa: E402
from brand_ai_readiness.analysis.structured import flatten_jsonld, schema_types  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract JSON-LD from HTML")
    parser.add_argument("html_file")
    args = parser.parse_args(argv)
    soup = parse_html(Path(args.html_file).read_text(encoding="utf-8"))
    out = []
    for parsed, error in json_ld_blocks(soup):
        if error or parsed is None:
            out.append({"error": error})
            continue
        for node in flatten_jsonld(parsed):
            out.append({"types": schema_types(node), "name": node.get("name")})
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
