from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
                if isinstance(value, list):
                    shown = ", ".join(str(item) for item in value[:8])
                    if len(value) > 8:
                        shown += f" (+{len(value) - 8} more)"
                    metric_bits.append(f"{key}={shown}")
                elif isinstance(value, dict):
                    # Render shallow maps readably rather than as a Python repr.
                    inner = ", ".join(f"{k}: {v}" for k, v in list(value.items())[:8])
                    metric_bits.append(f"{key}=({inner})")
                else:
                    metric_bits.append(f"{key}={value}")
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
