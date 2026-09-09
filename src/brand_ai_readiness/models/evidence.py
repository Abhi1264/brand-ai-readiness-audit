from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def _render_item(item: Any) -> str:
    """Render one metric value as prose.

    Evidence is a sentence a non-expert reads, so a container must never reach
    it as a Python repr. Dicts nested inside lists are the case that matters:
    the render-gap and canonical checks both report their examples that way.
    """
    if isinstance(item, dict):
        inner = ", ".join(f"{k}: {_render_item(v)}" for k, v in list(item.items())[:8])
        return f"({inner})"
    if isinstance(item, (list, tuple)):
        return ", ".join(_render_item(sub) for sub in list(item)[:8])
    return str(item)


class EvidencePayload(BaseModel):
    observation: str
    source_urls: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    quotes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def as_text(self) -> str:
        parts = [self.observation.strip()]
        if self.metrics:
            metric_bits = []
            for key, value in self.metrics.items():
                if isinstance(value, (list, tuple)):
                    shown = _render_item(value)
                    if len(value) > 8:
                        shown += f" (+{len(value) - 8} more)"
                    metric_bits.append(f"{key}={shown}")
                else:
                    metric_bits.append(f"{key}={_render_item(value)}")
            parts.append("Metrics: " + "; ".join(metric_bits) + ".")
        if self.source_urls:
            urls = ", ".join(self.source_urls[:8])
            extra = f" (+{len(self.source_urls) - 8} more)" if len(self.source_urls) > 8 else ""
            parts.append(f"Observed on: {urls}{extra}.")
        if self.quotes:
            quoted = "; ".join(f'"{q}"' for q in self.quotes[:4])
            parts.append(f"Quoted text: {quoted}.")
        if self.notes:
            parts.extend(self.notes)
        return " ".join(part for part in parts if part)
