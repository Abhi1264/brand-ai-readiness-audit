from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

TESTS = sorted(Path(__file__).resolve().parent.glob("test_*.py"))
_DEF = re.compile(r"^def (test_[A-Za-z0-9_]+)", re.M)


@pytest.mark.parametrize("path", TESTS, ids=lambda p: p.name)
def test_no_duplicate_test_names_in_a_module(path: Path):
    names = _DEF.findall(path.read_text(encoding="utf-8"))
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    assert not duplicates, (
        f"{path.name} defines these test names more than once, so only the last "
        f"of each actually runs: {duplicates}"
    )
