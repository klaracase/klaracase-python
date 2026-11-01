"""Logging: silent by default, informative at INFO, never leaks the token or a body."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import Klaracase
from klaracase._logging import LOGGER
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"
COVERAGE = {"status": 200, "headers": {}, "body_file": "../../examples/corpus.coverage.json"}


def client_for(server: MockServer, **kwargs: Any) -> Klaracase:
    kwargs.setdefault("sleep", lambda _s: None)
    return Klaracase(
        TOKEN, base_url=BASE, http_client=httpx2.Client(transport=server.transport()), **kwargs
    )


def serve(*responses: dict[str, Any]) -> MockServer:
    return MockServer(responses=list(responses), base_dir=FIXTURES / "conformance" / "cases")


@pytest.fixture(autouse=True)
def clean_logger() -> Iterator[None]:
    before = list(LOGGER.handlers)
    level = LOGGER.level
    yield
    LOGGER.handlers[:] = before
    LOGGER.setLevel(level)


def test_the_logger_has_a_null_handler_and_is_silent_by_default(
    capfd: pytest.CaptureFixture[str],
) -> None:
    assert any(isinstance(h, logging.NullHandler) for h in LOGGER.handlers)
    client_for(serve(COVERAGE)).corpus.coverage()
    assert capfd.readouterr().err == ""


def test_info_logs_the_request_and_the_retry(caplog: pytest.LogCaptureFixture) -> None:
    slow = {"status": 429, "headers": {}, "body_file": "../problems/rate_limited.retry_1s.json"}
    caplog.set_level(logging.INFO, logger="klaracase")
    client_for(serve(slow, COVERAGE)).corpus.coverage(top=3)
    lines = [r.getMessage() for r in caplog.records if r.name == "klaracase"]
    assert any(
        "GET /corpus/coverage -> 429" in m and "attempt 1" in m and "retry in" in m for m in lines
    )
    assert any("GET /corpus/coverage -> 200" in m and "attempt 2" in m for m in lines)
    assert all(r.levelno == logging.INFO for r in caplog.records if r.name == "klaracase")


def test_a_transport_retry_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="klaracase")
    client_for(serve({"drop_connection": True}, COVERAGE)).corpus.coverage()
    lines = [r.getMessage() for r in caplog.records]
    assert any("RemoteProtocolError" in m and "retry in" in m for m in lines)


def test_debug_shows_parameter_names_but_no_values_no_token_no_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="klaracase")
    secret_query = "Geheimnis Untreue Mandant Mueller"
    secret_text = "Der Mandant Mueller hat gestanden " * 5
    ok = {"status": 200, "headers": {}, "body_file": "../../examples/decisions.search.json"}
    check = {"status": 200, "headers": {}, "body_file": "../../examples/citation-checks.store.json"}
    client = client_for(serve(ok, check))
    client.decisions.search(secret_query, court="BGH")
    client.citation_checks.create(text=secret_text)
    output = "\n".join(r.getMessage() for r in caplog.records)
    assert "query=['court', 'query']" in output
    for forbidden in (TOKEN, "Bearer", secret_query, "Mandant", "Geheimnis", "BGH"):
        assert forbidden not in output


def test_a_deprecation_is_logged_once_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    klaracase.reset_deprecation_warnings()
    headers = {"deprecation": "true", "sunset": "Sat, 01 Aug 2026 00:00:00 GMT"}
    server = serve(
        {**COVERAGE, "headers": headers},
        {**COVERAGE, "headers": headers},
    )
    client = client_for(server, on_deprecation=lambda _n: None)
    client.corpus.coverage()
    client.corpus.coverage()
    warnings_logged = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings_logged) == 1
    assert "Sat, 01 Aug 2026" in warnings_logged[0].getMessage()
    klaracase.reset_deprecation_warnings()


def test_the_environment_variable_installs_a_stderr_handler_when_a_client_is_built(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KLARACASE_LOG", "info")
    client_for(serve(COVERAGE)).corpus.coverage()
    client_for(serve(COVERAGE)).corpus.coverage()
    env_handlers = [h for h in LOGGER.handlers if getattr(h, "_klaracase_env_handler", False)]
    assert len(env_handlers) == 1
    assert LOGGER.level == logging.INFO
    err = capfd.readouterr().err
    assert "klaracase INFO GET /corpus/coverage -> 200" in err
    assert TOKEN not in err


def test_debug_level_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KLARACASE_LOG", "DEBUG")
    client_for(serve(COVERAGE))
    assert LOGGER.level == logging.DEBUG


@pytest.mark.parametrize("value", ["", "warn", "verbose"])
def test_other_values_install_nothing(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("KLARACASE_LOG", value)
    before = list(LOGGER.handlers)
    client_for(serve(COVERAGE))
    assert LOGGER.handlers == before


def test_importing_the_package_installs_no_handler_and_prints_nothing() -> None:
    code = (
        "import logging, klaracase;"
        "print([type(h).__name__ for h in logging.getLogger('klaracase').handlers])"
    )
    env = {**os.environ, "KLARACASE_LOG": "debug"}
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    assert done.stdout.strip() == "['NullHandler']"
    assert done.stderr == ""
