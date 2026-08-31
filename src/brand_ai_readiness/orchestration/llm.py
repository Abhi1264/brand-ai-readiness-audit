from __future__ import annotations

import json
import logging
import os

import httpx

from brand_ai_readiness.models.findings import Finding

logger = logging.getLogger(__name__)


def polish_actions(findings: list[Finding]) -> list[Finding]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return findings
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "evidence": item.evidence_text(),
            "summary": item.suggested_action.summary,
            "details": item.suggested_action.details,
        }
        for item in findings
    ]
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite suggested_action.details to be more specific. "
                            "Do not add facts that are not in the provided evidence. "
                            "Return JSON list of {id, details}."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=20.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        rewritten = json.loads(content)
        by_id = {item["id"]: item.get("details") for item in rewritten if "id" in item}
        for finding in findings:
            extra = by_id.get(finding.id)
            if extra:
                finding.suggested_action.details = str(extra)
    except Exception as exc:  # noqa: BLE001 — polish must never fail the audit
        logger.info("LLM polish skipped: %s", exc)
    return findings


def maybe_polish(findings: list[Finding], enabled: bool) -> list[Finding]:
    if not enabled:
        return findings
    return polish_actions(findings)
