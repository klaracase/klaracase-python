"""Behavior that the conformance pack does not pin: types, errors, hooks, uploads."""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import io
import json
import pickle
import warnings
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import (
    ApiError,
    AsyncKlaracase,
    DocumentFailedError,
    DocumentTimeoutError,
    ForbiddenError,
    InsufficientCreditsError,
    Klaracase,
    KlaracaseError,
    KlaracaseTimeoutError,
    RateLimitError,
    TransportError,
    ValidationError,
)
from klaracase.types import DeprecationNotice
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = FIXTURES / "examples"
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"


def serve(*responses: dict[str, Any]) -> MockServer:
    return MockServer(responses=list(responses), base_dir=FIXTURES / "conformance" / "cases")


def ok(example: str, **headers: str) -> dict[str, Any]:
    return {
        "status": 200,
        "headers": {"x-klaracase-api-release": "0.95.0", **headers},
        "body_file": f"../../examples/{example}",
    }


def client_for(server: MockServer, **kwargs: Any) -> Klaracase:
    kwargs.setdefault("sleep", lambda _s: None)
    return Klaracase(
        TOKEN, base_url=BASE, http_client=httpx2.Client(transport=server.transport()), **kwargs
    )


def test_response_is_frozen_and_keeps_unknown_keys() -> None:
    server = serve(
        {
            "status": 200,
            "headers": {},
            "body": {"id": "r1", "status": "a_future_status", "future": {"x": 1}, "credits": None},
        }
    )
    run = client_for(server).citation_checks.get("r1")
    assert run.status == "a_future_status"
    assert run.extra == {"future": {"x": 1}}
    assert run.credits == klaracase.Credits()
    assert run.findings == []
    assert run.meta.api_release is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.id = "other"  # type: ignore[misc]


def test_to_dict_is_a_copy_of_the_body() -> None:
    server = serve(ok("citation-checks.show.json"))
    run = client_for(server).citation_checks.get("r1")
    body = json.loads((EXAMPLES / "citation-checks.show.json").read_text())
    assert run.to_dict() == body
    run.to_dict()["findings"].clear()
    assert run.to_dict() == body
    assert (run.credits.metered, run.credits.cost, run.credits.credits_remaining) == (True, 0, 18)
    assert run.findings[0].verdict == "verified_corpus"


def test_api_key_arguments_must_be_lists() -> None:
    client = client_for(serve())
    with pytest.raises(ValidationError) as caught:
        client.decisions.search("Untreue", cited_statutes="StGB")  # type: ignore[arg-type]
    assert caught.value.code == "client_validation"
    with pytest.raises(ValidationError):
        client.datapackages.create("0193b0c4-5f1e-7a2b-9c3d-4e5f6a7b8c9d")  # type: ignore[arg-type]


def test_upload_accepts_a_binary_file_object() -> None:
    server = serve(
        {
            "status": 202,
            "headers": {},
            "body_file": "../../examples/citation-check-documents.store.json",
        }
    )
    data = (FIXTURES / "conformance" / "files" / "schriftsatz.pdf").read_bytes()
    receipt = client_for(server).citation_check_documents.upload(
        io.BytesIO(data), filename="a.pdf", content_type="application/pdf"
    )
    assert receipt.status == "uploaded"
    assert receipt.meta.status == 202
    assert data in server.requests[0].body


def test_upload_retry_resends_the_same_bytes() -> None:
    problem = {"status": 503, "headers": {}, "body": {"code": "backend_unavailable"}}
    accepted = {
        "status": 202,
        "headers": {},
        "body_file": "../../examples/citation-check-documents.store.json",
    }
    server = serve(problem, accepted)
    client_for(server).citation_check_documents.upload(
        io.BytesIO(b"%PDF-1.7 hello"), filename="a.pdf", content_type="application/pdf"
    )
    assert len(server.requests) == 2
    assert all(b"%PDF-1.7 hello" in r.body for r in server.requests)


def test_default_deprecation_hook_warns_once_per_process() -> None:
    klaracase.reset_deprecation_warnings()
    headers = {"deprecation": "@1767225600", "sunset": "Sat, 01 Aug 2026 00:00:00 GMT"}
    server = serve(ok("corpus.coverage.json", **headers), ok("corpus.coverage.json", **headers))
    client = client_for(server)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        client.corpus.coverage()
        client.corpus.coverage()
    assert len(record) == 1
    assert issubclass(record[0].category, DeprecationWarning)
    assert "Sunset: Sat, 01 Aug 2026" in str(record[0].message)
    klaracase.reset_deprecation_warnings()
    with warnings.catch_warnings(record=True) as again:
        warnings.simplefilter("always")
        client_for(serve(ok("corpus.coverage.json", **headers))).corpus.coverage()
    assert len(again) == 1


def test_no_deprecation_headers_no_warning() -> None:
    klaracase.reset_deprecation_warnings()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client_for(serve(ok("corpus.coverage.json"))).corpus.coverage()


def test_custom_hook_receives_a_notice() -> None:
    klaracase.reset_deprecation_warnings()
    seen: list[DeprecationNotice] = []
    server = serve(ok("corpus.coverage.json", deprecation="true"))
    client_for(server, on_deprecation=seen.append).corpus.coverage()
    assert seen[0].deprecation == "true"
    assert seen[0].sunset is None
    assert seen[0].method == "GET"
    assert seen[0].url.endswith("/api/v1/corpus/coverage")


def test_error_properties_and_pickle() -> None:
    server = serve(
        {
            "status": 402,
            "headers": {"x-klaracase-api-release": "0.95.0"},
            "body_file": "../problems/insufficient_credits.json",
        }
    )
    with pytest.raises(InsufficientCreditsError) as caught:
        client_for(server).norms.get("§ 535 BGB")
    error = caught.value
    assert isinstance(error, KlaracaseError)
    assert (error.cost, error.balance) == (2, 0)
    clone = pickle.loads(pickle.dumps(error))
    assert type(clone) is InsufficientCreditsError
    assert clone.code == "insufficient_credits"
    assert clone.extra == error.extra
    assert str(clone) == str(error)
    assert copy.copy(error).status == 402


def test_forbidden_error_has_required_ability() -> None:
    server = serve(
        {"status": 403, "headers": {}, "body_file": "../problems/token_ability_missing.json"}
    )
    with pytest.raises(ForbiddenError) as caught:
        client_for(server).corpus.coverage()
    assert caught.value.required_ability == "citation-check"
    assert not isinstance(caught.value, PermissionError)


def test_rate_limit_error_falls_back_to_the_header_value() -> None:
    server = serve({"status": 429, "headers": {"retry-after": "45"}, "body_text": "slow down"})
    with pytest.raises(RateLimitError) as caught:
        client_for(server).corpus.coverage()
    assert caught.value.retry_after_seconds == 45
    assert caught.value.code == "unknown"
    assert len(server.requests) == 1


def test_error_hierarchy() -> None:
    assert issubclass(KlaracaseTimeoutError, TransportError)
    assert issubclass(DocumentFailedError, KlaracaseError)
    assert issubclass(DocumentTimeoutError, KlaracaseError)
    assert not issubclass(klaracase.ConfigurationError, KlaracaseError)
    assert not issubclass(ForbiddenError, OSError)


def test_transport_error_chains_the_httpx_exception() -> None:
    server = serve({"drop_connection": True})
    with pytest.raises(TransportError) as caught:
        client_for(server, max_retries=0).corpus.coverage()
    assert isinstance(caught.value.__cause__, httpx2.RemoteProtocolError)
    assert caught.value.status is None


def test_timeout_error_is_a_transport_error() -> None:
    server = serve({"status": 200, "headers": {}, "body": {}, "delay_seconds": 5})
    with pytest.raises(KlaracaseTimeoutError):
        client_for(server, max_retries=0, timeout=0.1).corpus.coverage()


def test_wait_until_ready_times_out_on_the_injected_clock() -> None:
    extracting = {"status": 200, "headers": {}, "body_file": "../bodies/documents.extracting.json"}
    server = serve(extracting)
    server.repeat_last = True
    ticks = iter([0.0, 0.0, 5.0, 5.0, 11.0, 11.0, 11.0, 11.0])
    slept: list[float] = []
    client = client_for(server, sleep=slept.append, monotonic=lambda: next(ticks))
    with pytest.raises(DocumentTimeoutError) as caught:
        client.citation_check_documents.wait_until_ready("d1", poll_interval=2.0, timeout=10.0)
    assert caught.value.code == "wait_timeout"
    assert caught.value.document.status == "extracting"
    assert slept


def test_wait_until_ready_bounds_the_last_sleep_by_the_remaining_time() -> None:
    extracting = {"status": 200, "headers": {}, "body_file": "../bodies/documents.extracting.json"}
    server = serve(extracting)
    server.repeat_last = True
    times = {"now": 0.0}
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        times["now"] += seconds

    client = client_for(server, sleep=fake_sleep, monotonic=lambda: times["now"])
    with pytest.raises(DocumentTimeoutError):
        client.citation_check_documents.wait_until_ready("d1", poll_interval=2.0, timeout=5.0)
    assert slept == [2.0, 2.0, 1.0]


def test_async_client_works_without_an_injected_client_closed_on_exit() -> None:
    async def go() -> None:
        async with AsyncKlaracase(TOKEN, base_url=BASE) as client:
            assert not client._http.is_closed
        assert client._http.is_closed

    asyncio.run(go())


def test_api_error_for_a_success_status_with_a_non_object_body() -> None:
    server = serve({"status": 200, "headers": {}, "body": [1, 2]})
    with pytest.raises(ApiError) as caught:
        client_for(server).corpus.coverage()
    assert caught.value.status == 200
    assert caught.value.code == "unknown"


def test_token_is_never_in_an_error_message() -> None:
    server = serve({"status": 401, "headers": {}, "body_file": "../problems/unauthenticated.json"})
    with pytest.raises(klaracase.AuthenticationError) as caught:
        client_for(server).corpus.coverage()
    assert TOKEN not in str(caught.value)
    assert TOKEN not in repr(caught.value.__dict__)
