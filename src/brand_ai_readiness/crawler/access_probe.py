from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

import httpx

from brand_ai_readiness.config import (
    AI_SEARCH_PROBE_AGENTS,
    AI_TRAINING_PROBE_AGENTS,
    BROWSER_PROBE_AGENT,
    AuditBudget,
)
from brand_ai_readiness.crawler.fetcher import fetch_bytes
from brand_ai_readiness.crawler.robots import RobotsPolicy
from brand_ai_readiness.models.snapshot import AccessProbeResult, BotClass

logger = logging.getLogger(__name__)

_HEAD_UNSUPPORTED = {400, 405, 501}

_PROBE_TIMEOUT_S = 8.0


def _probe_budget(budget: AuditBudget) -> AuditBudget:
    return replace(
        budget,
        max_retries=0,
        request_timeout_s=min(budget.request_timeout_s, _PROBE_TIMEOUT_S),
    )


async def _probe_one(
    client: httpx.AsyncClient,
    url: str,
    budget: AuditBudget,
    agent: str,
    user_agent: str,
    *,
    bot_class: BotClass,
    robots_allows: bool,
) -> AccessProbeResult:
    headers = {"User-Agent": user_agent}
    method = "HEAD"
    result = await fetch_bytes(client, url, budget, method="HEAD", headers=headers)
    if result.status_code in _HEAD_UNSUPPORTED or (result.status_code == 0 and result.error):
        method = "GET"
        result = await fetch_bytes(client, url, budget, method="GET", headers=headers)
    return AccessProbeResult(
        agent=agent,
        user_agent=user_agent,
        is_ai_crawler=bot_class != "browser",
        bot_class=bot_class,
        status_code=result.status_code,
        method=method,
        body_bytes=len(result.body),
        error=result.error,
        robots_allows=robots_allows,
    )


async def probe_access(
    client: httpx.AsyncClient,
    url: str,
    budget: AuditBudget,
    robots_policy: RobotsPolicy | None = None,
) -> list[AccessProbeResult]:
    budget = _probe_budget(budget)

    def _robots_verdict(agent_token: str) -> bool:
        if robots_policy is None:
            return True
        return robots_policy.allows_for(agent_token, url)

    jobs = [
        _probe_one(
            client,
            url,
            budget,
            "browser",
            BROWSER_PROBE_AGENT,
            bot_class="browser",
            robots_allows=True,
        )
    ]
    for agent, user_agent in AI_SEARCH_PROBE_AGENTS.items():
        jobs.append(
            _probe_one(
                client,
                url,
                budget,
                agent,
                user_agent,
                bot_class="search",
                robots_allows=_robots_verdict(agent),
            )
        )
    for agent, user_agent in AI_TRAINING_PROBE_AGENTS.items():
        jobs.append(
            _probe_one(
                client,
                url,
                budget,
                agent,
                user_agent,
                bot_class="training",
                robots_allows=_robots_verdict(agent),
            )
        )

    results = await asyncio.gather(*jobs, return_exceptions=True)
    probes: list[AccessProbeResult] = []
    for item in results:
        if isinstance(item, BaseException):
            logger.warning("access probe failed: %s", item)
            continue
        probes.append(item)
    return probes
