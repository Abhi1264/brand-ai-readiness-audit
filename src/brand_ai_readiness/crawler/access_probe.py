"""Diagnostic access probe: does the origin serve AI crawlers what it serves a browser?

robots.txt is a *request* that a crawler chooses to honor. Edge policy (WAF, CDN,
bot management) is *enforcement* that happens before content is served. The two
are configured independently and can disagree, so parsing robots.txt alone cannot
tell you whether an AI assistant can actually reach a page.

This module issues one bounded request per identity against a single URL and
records what came back. It never uses a probe identity to retrieve content the
audit's own user-agent was denied — a block is recorded as a finding, not
circumvented.
"""

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

# Status codes that mean "this origin does not answer HEAD", not "you are blocked".
_HEAD_UNSUPPORTED = {400, 405, 501}

# A diagnostic must never cost more than the crawl it informs. Origins that
# tarpit unfamiliar user-agents would otherwise multiply out to
# retries x timeout x (HEAD then GET) per agent, so the probe takes no retries
# and a shorter deadline; an agent that does not answer is recorded as unknown.
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
    # Some origins do not implement HEAD; that is not a block signal.
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
    """Fetch `url` once per identity and return what each was served.

    Deliberately not gated on robots.txt: a site that disallows the audit's own
    user-agent would otherwise yield no probe data at all, which is exactly the
    signal being measured. One URL, one request per agent.

    Search-class and training-class agents are both probed, but only the former
    can raise a finding: opting out of training while staying in search is a
    supported configuration, not a defect.
    """

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
    class_agents: tuple[tuple[BotClass, dict[str, str]], ...] = (
        ("search", AI_SEARCH_PROBE_AGENTS),
        ("training", AI_TRAINING_PROBE_AGENTS),
    )
    for bot_class, agents in class_agents:
        jobs += [
            _probe_one(
                client,
                url,
                budget,
                agent,
                user_agent,
                bot_class=bot_class,
                robots_allows=_robots_verdict(agent),
            )
            for agent, user_agent in agents.items()
        ]

    results = await asyncio.gather(*jobs, return_exceptions=True)
    probes: list[AccessProbeResult] = []
    for item in results:
        if isinstance(item, BaseException):
            logger.warning("access probe failed: %s", item)
            continue
        probes.append(item)
    return probes
