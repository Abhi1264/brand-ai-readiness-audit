"""Make `brand_ai_readiness` importable for skill scripts (installed package or sibling src/)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _ensure_importable() -> None:
    if importlib.util.find_spec("brand_ai_readiness") is not None:
        return
    for candidate in (SRC, ROOT):
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
    if importlib.util.find_spec("brand_ai_readiness") is None:
        raise ModuleNotFoundError(
            "brand_ai_readiness is not importable. This skill's scripts depend on "
            "the marketplace implementation. Install it from the marketplace root:\n"
            "    pip install -e .\n"
            "or run the script from a checkout that still contains src/."
        )


_ensure_importable()
