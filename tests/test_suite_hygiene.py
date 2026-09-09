from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

TESTS = sorted(Path(__file__).resolve().parent.glob("test_*.py"))
_DEF = re.compile(r"^def (test_[A-Za-z0-9_]+)", re.M)


@pytest.mark.parametrize("path", TESTS, ids=lambda p: p.name)
def test_no_duplicate_test_names_in_a_module(path: Path):
    """A repeated test name silently replaces the earlier one.

    Python rebinds the name, pytest collects only the survivor, and the original
    stops running without any warning. That happened here: appending a second
    test_sample_report_validates disabled an existing check, and the suite still
    reported green.
    """
    names = _DEF.findall(path.read_text(encoding="utf-8"))
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    assert not duplicates, (
        f"{path.name} defines these test names more than once, so only the last "
        f"of each actually runs: {duplicates}"
    )
