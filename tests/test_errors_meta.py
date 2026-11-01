"""Response headers on meta and errors, retryable, error codes, redaction and public names."""

from __future__ import annotations

import asyncio
import json
import pickle
import typing
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import AsyncKlaracase, Klaracase, KlaracaseError
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures"
PROBLEMS = sorted((FIXTURES / "conformance" / "problems").glob("*.json"))
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"


def serve(*responses: dict[str, Any]) -> MockServer:
    return MockServer(responses=list(responses), base_dir=FIXTURES / "conformance" / "cases")


def client_for(server: MockServer, **kwargs: Any) -> Klaracase:
    kwargs.setdefault("sleep", lambda _s: None)
    return Klaracase(
        TOKEN, base_url=BASE, http_client=httpx2.Client(transport=server.transport()), **kwargs
    )


def problem(status: int, name: str, **headers: str) -> dict[str, Any]:
    return {"status": status, "headers": headers, "body_file": f"../problems/{name}.json"}


def test_meta_headers_are_lower_case() -> None:
    server = serve(
        {
            "status": 200,
            "headers": {"X-Klaracase-Api-Release": "0.95.0", "X-RateLimit-Remaining": "59"},
            "body_file": "../../examples/corpus.coverage.json",
        }
    )
    meta = client_for(server).corpus.coverage().meta
    assert meta.headers["x-ratelimit-remaining"] == "59"
    assert meta.headers["x-klaracase-api-release"] == "0.95.0"
    assert meta.headers["content-type"] == "application/json"
    assert all(name == name.lower() for name in meta.headers)


def test_an_error_carries_headers_body_and_status_code() -> None:
    server = serve(problem(402, "insufficient_credits", **{"X-Request-Hint": "abc"}))
    with pytest.raises(klaracase.InsufficientCreditsError) as caught:
        client_for(server).norms.get("§ 1 BGB")
    error = caught.value
    assert error.status_code == error.status == 402
    assert error.response_headers["x-request-hint"] == "abc"
    assert error.body is not None
    assert error.body["code"] == "insufficient_credits"
    assert error.body["cost"] == error.extra["cost"]
    assert "InsufficientCreditsError(status=402, code='insufficient_credits'" in repr(error)


def test_a_non_problem_error_body() -> None:
    html = {"status": 502, "headers": {"content-type": "text/html"}, "body_text": "<html>"}
    with pytest.raises(klaracase.ApiError) as caught:
        client_for(serve(html)).corpus.coverage()
    assert caught.value.body is None
    assert caught.value.response_headers["content-type"] == "text/html"
    plain = {"status": 400, "headers": {}, "body": {"message": "bad"}}
    with pytest.raises(klaracase.ApiError) as again:
        client_for(serve(plain)).corpus.coverage()
    assert again.value.body == {"message": "bad"}
    assert again.value.code == "unknown"


def test_unprocessable_entity_error_is_validation_error() -> None:
    assert klaracase.UnprocessableEntityError is klaracase.ValidationError
    server = serve(problem(422, "validation_failed"))
    with pytest.raises(klaracase.UnprocessableEntityError) as caught:
        client_for(server).decisions.search("x")
    assert caught.value.status_code == 422


def test_retryable() -> None:
    cases = {
        "rate_limited": (429, True),
        "volume_cap": (429, False),
        "backend_unavailable": (503, True),
        "insufficient_credits": (402, False),
        "not_found": (404, False),
    }
    for name, (status, expected) in cases.items():
        server = serve(problem(status, name))
        server.repeat_last = True
        with pytest.raises(KlaracaseError) as caught:
            client_for(server, max_retries=0).corpus.coverage()
        assert caught.value.retryable is expected, name
    drop = serve({"drop_connection": True})
    with pytest.raises(klaracase.TransportError) as transport_error:
        client_for(drop, max_retries=0).corpus.coverage()
    assert transport_error.value.retryable is True


@pytest.mark.parametrize("path", PROBLEMS, ids=[p.stem for p in PROBLEMS])
def test_every_problem_code_in_the_pack_is_a_known_code(path: Path) -> None:
    code = json.loads(path.read_text(encoding="utf-8"))["code"]
    assert code in typing.get_args(klaracase.KnownErrorCode)


def test_the_sdk_own_codes_are_known() -> None:
    known = typing.get_args(klaracase.KnownErrorCode)
    for code in ("unknown", "client_validation", "wait_timeout", "response_shape"):
        assert code in known


def test_clients_redact_the_token_in_repr() -> None:
    client = Klaracase(TOKEN)
    text = repr(client) + repr(client._core)
    assert TOKEN not in text
    assert "<redacted>" in repr(client)
    assert "klaracase.de/api/v1" in repr(client)

    async def go() -> str:
        async with AsyncKlaracase(TOKEN) as aclient:
            return repr(aclient) + repr(aclient._core)

    assert TOKEN not in asyncio.run(go())
    client.close()


def test_public_classes_present_as_klaracase() -> None:
    for name in klaracase.__all__:
        obj = getattr(klaracase, name)
        if isinstance(obj, type):
            assert obj.__module__ == "klaracase", name


def test_public_objects_still_pickle_and_resolve_type_hints() -> None:
    decision = klaracase.Decision.from_dict(
        json.loads((FIXTURES / "examples" / "decisions.show.json").read_text(encoding="utf-8"))
    )
    clone = pickle.loads(pickle.dumps(decision))
    assert clone == decision
    hints = typing.get_type_hints(klaracase.Decision)
    assert "metadata" in hints
    error = pickle.loads(pickle.dumps(klaracase.NotFoundError(code="not_found", status=404)))
    assert isinstance(error, klaracase.NotFoundError)
