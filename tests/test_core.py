"""Unit tests for the transport core helpers."""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from pathlib import Path

import httpx2
import pytest

import klaracase
from klaracase._core import Core, Operation, query_pairs, quote_segment
from klaracase.errors import ConfigurationError
from klaracase.types import DecisionSearch


def make_core(**overrides: object) -> Core:
    params: dict[str, object] = {
        "token": "klc_your_token_here",
        "base_url": "https://klaracase.de/api/v1",
        "timeout": 30.0,
        "max_retries": 2,
        "user_agent_suffix": None,
        "on_deprecation": None,
        "monotonic": None,
    }
    params.update(overrides)
    return Core.create(**params)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        ("VIII ZR 271/17", "VIII%20ZR%20271%2F17"),
        ("§ 535 BGB", "%C2%A7%20535%20BGB"),
        ("Art. 6 DSGVO", "Art.%206%20DSGVO"),
        ("ECLI:DE:BGH:2001:151101U1STR185.01.0", "ECLI%3ADE%3ABGH%3A2001%3A151101U1STR185.01.0"),
        ("a~b-c_d.e", "a~b-c_d.e"),
        ("(x)!*'@&=+$,;", "%28x%29%21%2A%27%40%26%3D%2B%24%2C%3B"),
    ],
)
def test_quote_segment(value: str, encoded: str) -> None:
    assert quote_segment(value) == encoded


def test_query_pairs_omits_none_and_empty_and_keeps_false_and_zero() -> None:
    pairs = query_pairs(
        {"a": None, "b": False, "c": 0, "d": [], "e": ["x", "y"], "f": True, "g": "§ 1"}
    )
    assert pairs == [
        ("b", "false"),
        ("c", "0"),
        ("e[]", "x"),
        ("e[]", "y"),
        ("f", "true"),
        ("g", "§ 1"),
    ]


def test_request_kwargs_carry_headers_and_per_request_timeout() -> None:
    core = make_core(user_agent_suffix="acme/1.0", timeout=7)
    operation = Operation("GET", "/decisions/search", DecisionSearch, query=[("query", "x")])
    kwargs = core.request_kwargs(operation)
    assert kwargs["url"] == "https://klaracase.de/api/v1/decisions/search"
    assert kwargs["timeout"] == 7.0
    assert kwargs["headers"]["Authorization"] == "Bearer klc_your_token_here"
    assert kwargs["headers"]["Accept"] == "application/json"
    agent = kwargs["headers"]["User-Agent"]
    assert agent.startswith(f"klaracase-python/{klaracase.__version__} python/")
    assert agent.endswith(" acme/1.0")


def test_backoff_doubles_up_to_the_cap() -> None:
    ceilings: list[float] = []
    core = make_core()
    core.uniform = lambda low, high: ceilings.append(high) or high  # type: ignore[func-returns-value]
    for n in range(7):
        core.backoff(n)
    assert ceilings == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


@pytest.mark.parametrize(
    "overrides",
    [
        {"token": "   "},
        {"base_url": "klaracase.de/api/v1"},
        {"base_url": "ftp://klaracase.de"},
        {"max_retries": -1},
        {"timeout": 0},
    ],
)
def test_invalid_configuration_raises(
    overrides: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KLARACASE_API_TOKEN", raising=False)
    with pytest.raises(ConfigurationError):
        make_core(**overrides)


def test_base_url_trailing_slash_is_stripped() -> None:
    assert (
        make_core(base_url="https://example.test/api/v1/").base_url == "https://example.test/api/v1"
    )


def test_version_comes_from_the_version_module() -> None:
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert "version" not in pyproject["project"]
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/klaracase/_version.py"
    assert klaracase.__version__ == "0.1.0"
    assert importlib.metadata.version("klaracase") == klaracase.__version__


def test_default_http_client_is_built_and_closed() -> None:
    client = klaracase.Klaracase("klc_your_token_here")
    assert client._owns_http
    client.close()
    assert client._http.is_closed


def test_injected_http_client_is_not_closed() -> None:
    http = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200)))
    with klaracase.Klaracase("klc_your_token_here", http_client=http):
        pass
    assert not http.is_closed
    http.close()


def test_default_timeout_is_30_seconds_with_a_5_second_connect() -> None:
    core = make_core(timeout=klaracase.DEFAULT_TIMEOUT)
    assert core.timeout == httpx2.Timeout(30.0, connect=5.0)
    client = klaracase.Klaracase("klc_your_token_here")
    assert client._core.timeout == httpx2.Timeout(30.0, connect=5.0)
    client.close()


def test_timeout_accepts_a_timeout_object_and_rejects_nonsense() -> None:
    timeout = httpx2.Timeout(10.0, read=60.0)
    assert make_core(timeout=timeout).timeout is timeout
    with pytest.raises(ConfigurationError):
        make_core(timeout=True)


def test_the_per_request_timeout_reaches_the_http_client() -> None:
    seen: list[dict[str, float | None]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return httpx2.Response(200, json={})

    http = klaracase.DefaultHttpClient(transport=httpx2.MockTransport(handler), timeout=999.0)
    with klaracase.Klaracase("klc_your_token_here", http_client=http, timeout=7.0) as client:
        client.corpus.coverage()
    assert seen[0]["read"] == 7.0
    http.close()


def test_default_http_clients_carry_the_sdk_timeout() -> None:
    assert klaracase.DefaultHttpClient().timeout == httpx2.Timeout(30.0, connect=5.0)
    assert klaracase.DefaultAsyncHttpClient().timeout == httpx2.Timeout(30.0, connect=5.0)


def test_only_the_transport_module_imports_the_http_library() -> None:
    source = Path(klaracase.__file__).parent
    offenders = [
        path.name
        for path in source.glob("*.py")
        if path.name != "_transport.py"
        and re.search(r"^\s*(import|from)\s+httpx", path.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == []
