"""Run one conformance case against the sync or the async client."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

import httpx

import klaracase
from klaracase import AsyncKlaracase, Klaracase
from klaracase.errors import KlaracaseError
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures" / "conformance"
CASES = sorted((FIXTURES / "cases").glob("*.json"))
DEFAULT_TOKEN = "test_token_123"
BASE_URL = "http://127.0.0.1:1/api/v1"

CLASS_ALIASES = {
    "PermissionError": "ForbiddenError",
    "TimeoutError": "KlaracaseTimeoutError",
}

_TOKEN = re.compile(r'\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\["((?:[^"\\]|\\.)*)"\]')


def tokenize(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    position = 0
    while position < len(path):
        match = _TOKEN.match(path, position)
        assert match, f"bad path {path!r} at {position}"
        name, index, key = match.groups()
        tokens.append(name if name is not None else int(index) if index is not None else key)
        position = match.end()
    return tokens


def _step(node: Any, token: str | int) -> Any:
    if isinstance(node, dict):
        assert token in node, f"missing key {token!r} in {sorted(node)[:12]}"
        return node[token]
    if isinstance(node, list):
        assert isinstance(token, int)
        return node[token]
    assert hasattr(node, str(token)), f"no attribute {token!r} on {type(node).__name__}"
    return getattr(node, str(token))


def resolve(root: Any, path: str, *, error_root: bool = False) -> Any:
    tokens = tokenize(path)
    first, rest = tokens[0], tokens[1:]
    if error_root and first == "message" and not hasattr(root, "extra"):
        node = str(root)
    elif error_root and not hasattr(root, str(first)):
        node = _step(root.extra, first)
    else:
        node = _step(root, first)
    for token in rest:
        node = _step(node, token)
    return node


def matches(actual: Any, expected: Any) -> bool:
    if not (isinstance(expected, dict) and expected and all(k.startswith("$") for k in expected)):
        if isinstance(expected, bool) or isinstance(actual, bool):
            return actual is expected
        return bool(actual == expected)
    for key, want in expected.items():
        if key == "$type":
            kinds = {
                "number": (int, float),
                "string": str,
                "object": dict,
                "array": list,
                "boolean": bool,
            }
            if not isinstance(actual, kinds[want]) or (
                want == "number" and isinstance(actual, bool)
            ):
                return False
        elif key == "$min":
            if not isinstance(actual, (int, float)) or actual < want:
                return False
        elif key == "$length":
            if len(actual) != want:
                return False
        elif key == "$contains":
            if want not in actual:
                return False
        elif key == "$starts_with":
            if not actual.startswith(want):
                return False
        else:
            raise AssertionError(f"unknown matcher {key}")
    return True


def _load_args(args: dict[str, Any]) -> dict[str, Any]:
    loaded = {}
    for name, value in args.items():
        if isinstance(value, dict) and "$file" in value:
            loaded[name] = (FIXTURES / value["$file"]).read_bytes()
        else:
            loaded[name] = value
    return loaded


def _assert_request(case: dict[str, Any], server: MockServer) -> None:
    expect = case["expect"]
    count = expect["request_count"]
    if isinstance(count, dict):
        assert count["min"] <= len(server.requests) <= count["max"], len(server.requests)
    else:
        assert len(server.requests) == count
    wanted = expect["request"]
    if wanted is None:
        assert not server.requests
        return
    for seen in server.requests:
        assert seen.method == wanted["method"]
        assert seen.path == wanted["path"]
        assert seen.query_map() == wanted["query"]
        for name, value in wanted["headers"].items():
            actual = seen.headers.get(name)
            assert actual is not None, f"missing header {name}"
            if name == "user-agent":
                assert actual.startswith(value)
                if "user_agent_suffix" in wanted:
                    assert actual.endswith(" " + wanted["user_agent_suffix"])
            elif name == "content-type":
                assert actual.split(";")[0].strip().lower() == value
            else:
                assert actual == value
        if "content-type" not in wanted["headers"]:
            assert "content-type" not in seen.headers
        if "json" in wanted:
            assert seen.json() == wanted["json"]
        if "multipart" in wanted:
            assert seen.multipart() == wanted["multipart"]


def _assert_sleeps(case: dict[str, Any], slept: list[float]) -> None:
    wanted = case["expect"].get("sleeps")
    if wanted is None:
        assert slept == []
        return
    assert len(slept) == len(wanted), slept
    for seen, want in zip(slept, wanted, strict=True):
        if "exact" in want:
            assert seen == want["exact"]
        else:
            assert want["min"] <= seen <= want["max"], (seen, want)


def _last_body(case: dict[str, Any], server: MockServer) -> Any:
    spec = case["responses"][-1]
    if "body" in spec:
        return spec["body"]
    return json.loads((server.base_dir / spec["body_file"]).read_text())


def _assert_success(
    case: dict[str, Any], server: MockServer, result: Any, notices: list[Any]
) -> None:
    expected = case["expect_result"]
    for path, want in expected.get("assert", {}).items():
        actual = resolve(result, path)
        assert matches(actual, want), f"{path}: expected {want!r}, got {actual!r}"
    if expected.get("body_roundtrip"):
        assert result.to_dict() == _last_body(case, server)
    if "deprecation_warning" in expected:
        assert bool(notices) == expected["deprecation_warning"]
    if "deprecation_warning_count" in expected:
        assert len(notices) == expected["deprecation_warning_count"]
    if "deprecation" in expected:
        notice = notices[0]
        for name, value in expected["deprecation"].items():
            assert getattr(notice, name) == value


def _assert_error(case: dict[str, Any], server: MockServer, error: BaseException) -> None:
    expected = case["expect_result"]
    name = CLASS_ALIASES.get(expected["class"], expected["class"])
    expected_cls = getattr(klaracase, name)
    assert isinstance(error, expected_cls), f"{type(error).__name__} is not a {name}"
    if name == "ConfigurationError":
        assert not isinstance(error, KlaracaseError)
    else:
        assert isinstance(error, KlaracaseError)
        assert error.code == expected["code"]
        assert error.status == expected["status"]
    for path, want in expected.get("fields", {}).items():
        actual = resolve(error, path, error_root=True)
        assert matches(actual, want), f"{path}: expected {want!r}, got {actual!r}"
    responses = case["responses"]
    served = responses[min(len(server.requests), len(responses)) - 1] if responses else {}
    if (
        isinstance(error, KlaracaseError)
        and served.get("body_file", "").endswith(".json")
        and "status" in served
    ):
        body = json.loads((server.base_dir / served["body_file"]).read_text())
        if isinstance(body, dict) and isinstance(body.get("code"), str):
            for key in ("type", "title", "detail", "status", "code"):
                assert getattr(error, key) == body[key]
            release = served["headers"].get("x-klaracase-api-release")
            assert error.api_release == release
            assert error.extra == {
                k: v
                for k, v in body.items()
                if k not in {"type", "title", "detail", "status", "code"}
            }


def _client_kwargs(case: dict[str, Any], server: MockServer) -> dict[str, Any]:
    options = case["sdk"].get("options", {})
    base_url = BASE_URL + ("/" if options.get("base_url_trailing_slash") else "")
    kwargs: dict[str, Any] = {
        "token": options.get("token", DEFAULT_TOKEN),
        "base_url": base_url,
        "user_agent_suffix": options.get("user_agent_suffix"),
    }
    for name in ("max_retries", "timeout"):
        if name in options:
            kwargs[name] = options[name]
    return kwargs


def run_case(case: dict[str, Any], mode: str, monkeypatch: Any) -> None:
    monkeypatch.delenv("KLARACASE_API_TOKEN", raising=False)
    for name, value in case["sdk"].get("env", {}).items():
        monkeypatch.setenv(name, value)
    klaracase.reset_deprecation_warnings()
    server = MockServer(
        responses=case["responses"],
        base_dir=FIXTURES / "cases",
        repeat_last=case.get("runner", {}).get("repeat_last_response", False),
    )
    real_clock = case.get("runner", {}).get("real_clock", False)
    slept: list[float] = []
    notices: list[Any] = []
    kwargs = _client_kwargs(case, server)
    kwargs["on_deprecation"] = notices.append
    sdk = case["sdk"]
    args = _load_args(sdk.get("args", {}))
    repeat = sdk.get("repeat", 1)
    outcomes: list[Any] = []

    def record(outcome: Any) -> None:
        outcomes.append(outcome)

    if mode == "sync":
        if not real_clock:
            kwargs["sleep"] = slept.append
        try:
            with Klaracase(http_client=httpx.Client(transport=server.transport()), **kwargs) as c:
                target = c if sdk["group"] is None else getattr(c, sdk["group"])
                method = c.search if sdk["group"] is None else getattr(target, sdk["method"])
                for _ in range(repeat):
                    record(method(**args))
        except Exception as exc:
            record(exc)
    else:
        if not real_clock:

            async def fake_sleep(seconds: float) -> None:
                slept.append(seconds)

            kwargs["sleep"] = fake_sleep

        async def go() -> None:
            try:
                async with AsyncKlaracase(
                    http_client=httpx.AsyncClient(transport=server.transport()), **kwargs
                ) as c:
                    target = c if sdk["group"] is None else getattr(c, sdk["group"])
                    method = c.search if sdk["group"] is None else getattr(target, sdk["method"])
                    for _ in range(repeat):
                        record(await method(**args))
            except Exception as exc:
                record(exc)

        asyncio.run(go())

    _assert_request(case, server)
    if not real_clock:
        _assert_sleeps(case, slept)
    expected = case["expect_result"]
    if expected["kind"] == "error":
        assert isinstance(outcomes[-1], BaseException), f"expected an error, got {outcomes[-1]!r}"
        _assert_error(case, server, outcomes[-1])
        return
    for outcome in outcomes:
        assert not isinstance(outcome, BaseException), repr(outcome)
        assert is_dataclass(outcome)
        _assert_success(case, server, outcome, notices)
