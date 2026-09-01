"""Make `brand_ai_readiness` importable for the skill scripts.

Resolution order:

1. An installed package (``pip install .`` / ``pip install -e .``). This is the
   portable case: a skill folder copied elsewhere still runs, because the
   implementation is on the normal import path.
2. The sibling ``src/`` tree, for running straight from a checkout with nothing
   installed.

If neither works the failure is raised with the command that fixes it, rather
than surfacing as a bare ModuleNotFoundError from inside a skill script.
"""

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
