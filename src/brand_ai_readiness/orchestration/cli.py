from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from brand_ai_readiness.config import AuditBudget
from brand_ai_readiness.crawler.urls import site_label
from brand_ai_readiness.orchestration.compose import run_audit
from brand_ai_readiness.orchestration.progress import make_progress
from brand_ai_readiness.orchestration.render_markdown import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a website for AI discoverability and on-site engagement (read-only)."
    )
    parser.add_argument("url", help="Public website URL to audit")
    parser.add_argument("-o", "--output", help="Write the report to this path (default: stdout)")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="json is the report contract; markdown renders the same data for a human reader",
    )
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-renders", type=int, default=8)
    parser.add_argument("--no-render", action="store_true", help="Skip Playwright even if installed")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--llm-polish", action="store_true", help="Optional wording polish if OPENAI_API_KEY is set")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress the live progress display (stderr-only; auto-disables when piped)",
    )
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
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    reporter = make_progress(not args.no_progress and not args.verbose, site_label(url))
    try:
        report = asyncio.run(run_audit(url, budget_from_args(args), reporter))
    except KeyboardInterrupt:
        reporter.failed("interrupted")
        return 130
    except Exception as exc:  # noqa: BLE001
        reporter.failed(str(exc))
        raise
    payload = report.model_dump_public()
    reporter.done(payload)
    if args.format == "markdown":
        text = render_markdown(payload)
    else:
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
