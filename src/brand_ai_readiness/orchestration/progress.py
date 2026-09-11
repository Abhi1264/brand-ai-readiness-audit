from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import TextIO

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_PHASES: tuple[tuple[str, str], ...] = (
    ("robots", "robots.txt"),
    ("probe", "AI-crawler probe"),
    ("crawl", "crawling"),
    ("render", "rendering"),
    ("analyse", "analysing"),
    ("report", "building report"),
)
_ORDER = tuple(key for key, _ in _PHASES)
_LABELS = dict(_PHASES)
_SEVERITY_ORDER = ("critical", "high", "medium", "low")


def _supports_ansi(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


class Progress:
    def phase(self, key: str, detail: str = "") -> None: ...
    def detail(self, key: str, detail: str) -> None: ...
    def skip(self, key: str, why: str = "") -> None: ...
    def tick(self, done: int, queued: int = 0) -> None: ...
    def done(self, report: dict) -> None: ...
    def failed(self, message: str) -> None: ...


@dataclass
class TerminalProgress(Progress):
    stream: TextIO = field(default_factory=lambda: sys.stderr)
    site: str = ""
    _ansi: bool = field(default=False, init=False)
    _state: dict[str, str] = field(default_factory=dict, init=False)
    _details: dict[str, str] = field(default_factory=dict, init=False)
    _current: str = field(default="", init=False)
    _frame: int = field(default=0, init=False)
    _lines: int = field(default=0, init=False)
    _start: float = field(default_factory=time.monotonic, init=False)

    def __post_init__(self) -> None:
        self._ansi = _supports_ansi(self.stream)
        self._state = {key: "pending" for key in _ORDER}
        if self.site:
            self._write(f"\n  auditing {self.site}\n\n")

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text)
            self.stream.flush()
        except (ValueError, OSError):
            pass

    def _marker(self, key: str) -> str:
        state = self._state[key]
        if state == "done":
            return "\033[32m✓\033[0m" if self._ansi else "done"
        if state == "skipped":
            return "\033[90m–\033[0m" if self._ansi else "skip"
        if state == "active":
            return _SPINNER[self._frame % len(_SPINNER)] if self._ansi else " .. "
        return " " if self._ansi else "    "

    def _render(self) -> None:
        if not self._ansi:
            return
        if self._lines:
            self._write(f"\033[{self._lines}A")
        out = []
        for key in _ORDER:
            label = _LABELS[key]
            detail = self._details.get(key, "")
            dim_label = label if self._state[key] != "pending" else f"\033[90m{label}\033[0m"
            line = f"  {self._marker(key)} {dim_label:<22}"
            if detail:
                line += f"\033[90m{detail}\033[0m"
            out.append(line + "\033[K")
        self._write("\n".join(out) + "\n")
        self._lines = len(out)

    def phase(self, key: str, detail: str = "") -> None:
        if key not in self._state:
            return
        for previous in _ORDER:
            if previous == key:
                break
            if self._state[previous] == "active":
                self._state[previous] = "done"
        self._state[key] = "active"
        self._current = key
        if detail:
            self._details[key] = detail
        if self._ansi:
            self._render()
        else:
            self._write(f"  {_LABELS[key]}{(': ' + detail) if detail else ''}\n")

    def detail(self, key: str, detail: str) -> None:
        if key not in self._state:
            return
        self._details[key] = detail
        if self._ansi:
            self._render()

    def skip(self, key: str, why: str = "") -> None:
        if key not in self._state:
            return
        self._state[key] = "skipped"
        if why:
            self._details[key] = why
        if self._ansi:
            self._render()
        else:
            self._write(f"  {_LABELS[key]}: {why or 'skipped'}\n")

    def tick(self, done: int, queued: int = 0) -> None:
        self._frame += 1
        queued_text = f" · {queued} queued" if queued else ""
        self.detail("crawl", f"{done} page{'' if done == 1 else 's'}{queued_text}")

    def failed(self, message: str) -> None:
        if self._current and self._state.get(self._current) == "active":
            self._state[self._current] = "skipped"
            self._details[self._current] = message[:60]
        if self._ansi:
            self._render()
        else:
            self._write(f"  failed: {message}\n")

    def done(self, report: dict) -> None:
        for key in _ORDER:
            if self._state[key] == "active":
                self._state[key] = "done"
        if self._ansi:
            self._render()
        self._write(summarise(report, elapsed=time.monotonic() - self._start, ansi=self._ansi))


def _bar(counts: dict, ansi: bool) -> str:
    colours = {"critical": "31", "high": "33", "medium": "36", "low": "90"}
    parts = []
    for name in _SEVERITY_ORDER:
        value = counts.get(name, 0)
        text = f"{name.upper()} {value}"
        if ansi and value:
            text = f"\033[{colours[name]}m{text}\033[0m"
        elif ansi:
            text = f"\033[90m{text}\033[0m"
        parts.append(text)
    return "   ".join(parts)


def summarise(report: dict, *, elapsed: float | None = None, ansi: bool = False) -> str:
    summary = report.get("summary") or {}
    coverage = report.get("coverage") or {}
    scores = report.get("scores") or {}
    rule = "  " + "─" * 62 + "\n" if ansi else "  " + "-" * 62 + "\n"

    head = f"{report.get('site', 'site')}"
    if report.get("site_type"):
        head += f" · {report['site_type']}"
        head += f" · {coverage.get('pages_crawled', 0)} pages crawled"
    if elapsed is not None:
        head += f" · {elapsed:.1f}s"

    out = ["\n", rule, f"  {head}\n", "\n", "  " + _bar(summary, ansi) + "\n"]
    if scores:
        out.append(
            f"\n  discoverability {scores.get('ai_discoverability_score', '-')}"
            f"   engagement {scores.get('engagement_score', '-')}"
            f"   overall {scores.get('overall_score', '-')}\n"
        )
    findings = report.get("findings") or []
    if findings:
        top = findings[0]
        action = (top.get("suggested_action") or {}).get("summary", "")
        out.append(f"\n  first fix  {top.get('title', '')}\n")
        if action:
            out.append(f"             {action}\n")
    else:
        out.append("\n  no defects found in what could be checked\n")
    for line in coverage.get("limitations", [])[:2]:
        out.append(f"\n  note  {line}\n")
    out.append(rule)
    return "".join(out)


def make_progress(enabled: bool, site: str) -> Progress:
    return TerminalProgress(site=site) if enabled else Progress()
