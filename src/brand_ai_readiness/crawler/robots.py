from __future__ import annotations

import logging
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from brand_ai_readiness.config import DEFAULT_USER_AGENT
from brand_ai_readiness.crawler.urls import origin_of
from brand_ai_readiness.models.snapshot import RobotsInfo

logger = logging.getLogger(__name__)


class RobotsPolicy:
    def __init__(self, info: RobotsInfo, parser: RobotFileParser | None, user_agent: str) -> None:
        self.info = info
        self._parser = parser
        self.user_agent = user_agent

    def allows(self, url: str) -> bool:
        return self.allows_for(self.user_agent, url)

    def allows_for(self, user_agent: str, url: str) -> bool:
        if self._parser is None:
            return True
        try:
            return bool(self._parser.can_fetch(user_agent, url))
        except Exception as exc:
            logger.warning("robots check failed for %s: %s", url, exc)
            return True


def _disallow_patterns(raw: str) -> list[str]:
    patterns: list[str] = []
    in_star = False
    for line in raw.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            in_star = value == "*"
        elif key == "disallow" and in_star and value:
            patterns.append(value)
    return patterns


def _strip_html_tail(raw: str) -> str:
    for marker in ("<!doctype", "<html", "<HTML"):
        idx = raw.find(marker)
        if idx > 0:
            return raw[:idx]
    return raw


def parse_robots(raw: str, robots_url: str, user_agent: str = DEFAULT_USER_AGENT) -> RobotsPolicy:
    raw = _strip_html_tail(raw)
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parse_error: str | None = None
    try:
        parser.parse(raw.splitlines())
    except Exception as exc:
        parse_error = str(exc)
        parser = None
    sitemaps = [
        line.split(":", 1)[1].strip()
        for line in raw.splitlines()
        if line.strip().lower().startswith("sitemap:")
    ]
    info = RobotsInfo(
        url=robots_url,
        available=True,
        raw=raw,
        sitemaps=sitemaps,
        disallow_patterns=_disallow_patterns(raw),
        parse_error=parse_error,
    )
    return RobotsPolicy(info, parser, user_agent)


def empty_robots(start_url: str) -> RobotsPolicy:
    origin = origin_of(start_url)
    info = RobotsInfo(url=urljoin(origin + "/", "robots.txt"), available=False)
    return RobotsPolicy(info, None, DEFAULT_USER_AGENT)


def allows_url(raw_robots: str, url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    policy = parse_robots(raw_robots, "https://example.com/robots.txt", user_agent)
    return policy.allows(url)
