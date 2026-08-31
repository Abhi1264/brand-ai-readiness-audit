"""Judge-facing CLI: brand-audit URL [-o report.json]."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.orchestration.compose import run_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a website for AI discoverability and on-site engagement (read-only)."
    )
    parser.add_argument("url", help="Public website URL to audit")
    parser.add_argument("-o", "--output", help="Write JSON report to this path (default: stdout)")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-renders", type=int, default=8)
    parser.add_argument("--no-render", action="store_true", help="Skip Playwright even if installed")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--llm-polish", action="store_true", help="Optional wording polish if OPENAI_API_KEY is set")
    parser.add_argument("--verbose", action="store_true")
    return parser


def budget_from_args(args: argparse.Namespace) -> AuditBudget:
    return AuditBudget(
        max_pages=args.max_pages,
        max_renders=args.max_renders,
        request_timeout_s=args.timeout,
        max_concurrency=args.concurrency,
        enable_render=not args.no_render,
        enable_llm_polish=args.llm_polish,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        report = asyncio.run(run_audit(url, budget_from_args(args)))
    except KeyboardInterrupt:
        return 130
    payload = report.model_dump_public()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        path = Path(args.output)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {path} ({payload['summary']['total_findings']} findings)", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
