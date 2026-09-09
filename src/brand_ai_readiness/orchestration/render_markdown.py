"""Render an audit report as Markdown.

The JSON report is the contract; this is the same data arranged for a person.
The rubric asks for a report "a non-expert could act on", and a non-expert
cannot act on a JSON object: they need to know what to fix first, why it matters
in one sentence, what the evidence was, and where to change it.

Nothing is computed here. Every value comes from the report, so the Markdown and
the JSON can never disagree.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_LABEL = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}


def _fmt_when(value: str) -> str:
    return value.replace("T", " ").replace("Z", " UTC")


def _scores_table(scores: dict[str, Any] | None) -> list[str]:
    if not scores:
        return []
    out = [
        "## Scores",
        "",
        "| AI discoverability | On-site engagement | Overall |",
        "| ---: | ---: | ---: |",
        f"| {scores.get('ai_discoverability_score', '-')} "
        f"| {scores.get('engagement_score', '-')} "
        f"| {scores.get('overall_score', '-')} |",
        "",
    ]
    components = scores.get("components") or {}
    if components:
        out += ["<details><summary>Component scores</summary>", ""]
        out += ["| Component | Score |", "| --- | ---: |"]
        for name, value in components.items():
            out.append(f"| {name.replace('_', ' ')} | {value} |")
        out += ["", "</details>", ""]
    return out


def _finding_block(index: int, finding: dict[str, Any]) -> list[str]:
    severity = finding.get("severity", "low")
    action = finding.get("suggested_action") or {}
    out = [
        f"### {index}. {finding.get('title', 'Untitled finding')}",
        "",
        f"`{_SEVERITY_LABEL.get(severity, severity.upper())}`"
        f" · `{finding.get('id', '')}`"
        + (f" · {finding['category']}" if finding.get("category") else "")
        + (
            f" · confidence {finding['confidence']:.0%}"
            if isinstance(finding.get("confidence"), (int, float))
            else ""
        ),
        "",
    ]
    if finding.get("mechanism"):
        out += [f"**Why this happens.** {finding['mechanism']}", ""]
    if finding.get("impact"):
        out += [f"**What it costs.** {finding['impact']}", ""]
    if finding.get("evidence"):
        out += ["**Evidence.**", "", f"> {finding['evidence']}", ""]
    if action.get("summary"):
        priority = action.get("priority", severity)
        out += [f"**Fix ({priority} priority).** {action['summary']}", ""]
    if action.get("details"):
        out += [action["details"], ""]
    if action.get("implementation_direction"):
        out += [f"*Where to change it:* {action['implementation_direction']}", ""]
    if action.get("rationale"):
        out += [f"*Why we are confident:* {action['rationale']}", ""]
    urls = finding.get("source_urls") or []
    # as_text() already appends "Observed on: ..." to the evidence, so repeating
    # the same URLs underneath it is noise.
    if urls and "Observed on:" not in str(finding.get("evidence", "")):
        shown = ", ".join(urls[:5])
        more = f" (+{len(urls) - 5} more)" if len(urls) > 5 else ""
        out += [f"*Observed on:* {shown}{more}", ""]
    return out


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    findings = sorted(
        report.get("findings") or [],
        key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "low"), 9),
    )

    lines = [
        f"# AI-readiness audit — {report.get('site', 'unknown site')}",
        "",
        f"Audited {_fmt_when(str(report.get('audited_at', '')))}"
        + (f" · inferred site type: **{report['site_type']}**" if report.get("site_type") else ""),
        "",
        "| Severity | Count |",
        "| --- | ---: |",
        f"| Critical | {summary.get('critical', 0)} |",
        f"| High | {summary.get('high', 0)} |",
        f"| Medium | {summary.get('medium', 0)} |",
        f"| Low | {summary.get('low', 0)} |",
        f"| **Total** | **{summary.get('total_findings', 0)}** |",
        "",
    ]
    lines += _scores_table(report.get("scores"))

    if findings:
        lines += ["## Start here", ""]
        for position, finding in enumerate(findings[:3], start=1):
            action = (finding.get("suggested_action") or {}).get("summary", "")
            lines.append(
                f"{position}. **{finding.get('title', '')}** "
                f"(`{_SEVERITY_LABEL.get(finding.get('severity', 'low'), '')}`) — {action}"
            )
        lines += ["", "Findings below are ordered so the first one is the first fix.", ""]
        lines += ["## Findings", ""]
        for position, finding in enumerate(findings, start=1):
            lines += _finding_block(position, finding)
    else:
        lines += [
            "## Findings",
            "",
            "No defects were detected in what this audit was able to check. "
            "See the coverage note below for what that did and did not include.",
            "",
        ]

    proactive = report.get("proactive_recommendations") or []
    if proactive:
        lines += [
            "## Opportunities beyond the defects found",
            "",
            "These are not problems. They are changes that would strengthen how the brand is "
            "found, read and quoted.",
            "",
        ]
        for item in proactive:
            lines += [
                f"- **{item.get('summary', '')}**",
                f"  - Why it matters: {item.get('why_it_matters', '')}",
                f"  - What to change: {item.get('what_to_change', '')}",
                f"  - Expected benefit: {item.get('expected_benefit', '')}",
            ]
        lines.append("")

    coverage = report.get("coverage") or {}
    if coverage:
        lines += [
            "## What this audit checked, and what it could not",
            "",
            f"Crawled **{coverage.get('pages_crawled', 0)}** of "
            f"{coverage.get('pages_discovered', 0)} discovered URLs · "
            f"rendered {coverage.get('pages_rendered', 0)} · "
            f"rendering `{coverage.get('rendering_status', 'unknown')}` · "
            f"corroboration `{coverage.get('corroboration_status', 'unknown')}`"
            + (
                f" · AI-crawler probe `{coverage['access_probe_status']}`"
                if coverage.get("access_probe_status")
                else ""
            ),
            "",
        ]
        limitations = coverage.get("limitations") or []
        if limitations:
            lines.append("Limits on what can be concluded from this run:")
            lines.append("")
            lines += [f"- {line}" for line in limitations]
            lines.append("")
        lines += [
            "Findings describe the pages that were crawled. A signal not observed on those pages "
            "is reported as absent from them, never as absent from the whole site.",
            "",
        ]

    lines += [
        "---",
        "",
        "Generated by the `brand-ai-readiness-audit` skill marketplace. Read-only: this audit "
        "reports and recommends, and never modifies the site it audits.",
        "",
    ]
    return "\n".join(lines)
