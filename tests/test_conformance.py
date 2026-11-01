"""The shared conformance pack, run for the sync and the async client."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conformance import CASES, run_case


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_conformance_case(path: Any, mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    case = json.loads(path.read_text())
    assert case["name"] == path.stem
    run_case(case, mode, monkeypatch)


def test_pack_has_106_cases() -> None:
    assert len(CASES) == 106
