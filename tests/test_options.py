"""Per-call options, with_options, date and upload arguments, and the raw escape hatches."""

from __future__ import annotations

import asyncio
import datetime
import io
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import AsyncKlaracase, Klaracase, ValidationError
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"
COVERAGE = {
    "status": 200,
    "headers": {"x-klaracase-api-release": "0.95.0"},
    "body_file": "../../examples/corpus.coverage.json",
}
STORE = {
    "status": 202,
    "headers": {},
    "body_file": "../../examples/citation-check-documents.store.json",
}


def example(name: str) -> dict[str, Any]:
    return {"status": 200, "headers": {}, "body_file": f"../../examples/{name}.json"}


def serve(*responses: dict[str, Any]) -> MockServer:
    return MockServer(responses=list(responses), base_dir=FIXTURES / "conformance" / "cases")


def client_for(server: MockServer, **kwargs: Any) -> Klaracase:
    kwargs.setdefault("sleep", lambda _s: None)
    return Klaracase(
        TOKEN, base_url=BASE, http_client=httpx2.Client(transport=server.transport()), **kwargs
    )


def test_a_per_call_timeout_overrides_the_client_timeout() -> None:
    seen: list[dict[str, float | None]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return httpx2.Response(200, json={})

    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    client = Klaracase(TOKEN, http_client=http, timeout=7.0)
    client.corpus.coverage()
    client.corpus.coverage(timeout=2.5)
    client.corpus.coverage(timeout=httpx2.Timeout(9.0, connect=1.0))
    assert [s["read"] for s in seen] == [7.0, 2.5, 9.0]
    assert seen[2]["connect"] == 1.0


def test_a_bad_per_call_timeout_is_a_configuration_error() -> None:
    client = client_for(serve(COVERAGE))
    with pytest.raises(klaracase.ConfigurationError):
        client.corpus.coverage(timeout=0)


def test_extra_headers_are_added_and_win_case_insensitively() -> None:
    server = serve(COVERAGE)
    client_for(server).corpus.coverage(extra_headers={"X-Trace": "abc", "accept": "text/plain"})
    headers = server.requests[0].headers
    assert headers["x-trace"] == "abc"
    assert headers["accept"] == "text/plain"
    assert headers["authorization"] == f"Bearer {TOKEN}"


def test_extra_query_is_added_and_replaces_a_parameter_of_the_same_name() -> None:
    server = serve(COVERAGE)
    client_for(server).corpus.coverage(top=5, extra_query={"top": 7, "flag": True, "x": "y"})
    assert server.requests[0].query_map() == {"top": "7", "flag": "true", "x": "y"}


def test_with_options_returns_a_new_client_that_shares_the_transport() -> None:
    server = serve(COVERAGE, COVERAGE)
    client = client_for(server)
    other = client.with_options(max_retries=0, timeout=3.0, extra_headers={"X-Team": "a"})
    assert other is not client
    assert other._core.max_retries == 0
    assert client._core.max_retries == 2
    assert other._core.timeout == 3.0
    assert other._http is client._http
    other.corpus.coverage()
    client.corpus.coverage()
    assert server.requests[0].headers["x-team"] == "a"
    assert "x-team" not in server.requests[1].headers
    other.close()
    assert not client._http.is_closed
    client.close()


def test_with_options_headers_add_up() -> None:
    client = client_for(serve(COVERAGE))
    twice = client.with_options(extra_headers={"A": "1"}).with_options(extra_headers={"B": "2"})
    assert dict(twice._core.extra_headers) == {"A": "1", "B": "2"}
    with pytest.raises(klaracase.ConfigurationError):
        client.with_options(max_retries=-1)


def test_the_async_client_has_the_same_options() -> None:
    async def go() -> None:
        server = serve(COVERAGE)
        http = httpx2.AsyncClient(transport=server.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            other = client.with_options(extra_headers={"X-Team": "a"}, max_retries=1)
            await other.corpus.coverage(extra_query={"k": "v"}, timeout=4.0)
        assert server.requests[0].headers["x-team"] == "a"
        assert server.requests[0].query_map() == {"k": "v"}
        assert other._core.max_retries == 1

    asyncio.run(go())


def test_date_arguments_accept_a_date_a_datetime_or_a_string() -> None:
    server = serve(
        example("decisions.search"), example("decisions.show"), example("citation-checks.store")
    )
    client = client_for(server)
    client.decisions.search("q", date_from=datetime.date(2026, 1, 2), date_to="2026-02-03")
    client.decisions.get("x", date=datetime.datetime(2026, 5, 6, 23, 59, tzinfo=datetime.UTC))
    client.citation_checks.create(text="t" * 60, reference_date=datetime.date(2026, 10, 1))
    first, second, third = server.requests
    assert first.query_map() == {"query": "q", "date_from": "2026-01-02", "date_to": "2026-02-03"}
    assert second.query_map() == {"date": "2026-05-06"}
    assert third.json()["reference_date"] == "2026-10-01"


def test_a_date_of_the_wrong_type_is_refused_before_any_request() -> None:
    server = serve()
    with pytest.raises(ValidationError) as caught:
        client_for(server).decisions.search("q", date_from=20260102)  # type: ignore[arg-type]
    assert caught.value.code == "client_validation"
    assert server.requests == []


def test_cited_statutes_accepts_a_string_outside_the_known_list() -> None:
    server = serve(COVERAGE)
    client_for(server).decisions.search("q", cited_statutes=["StGB", "UWG"])
    assert server.requests[0].query_map()["cited_statutes[]"] == ["StGB", "UWG"]


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("brief.pdf", "application/pdf"),
        ("brief.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("brief.md", "text/markdown"),
        ("brief.TXT", "text/plain"),
        ("brief.unknownext", "application/octet-stream"),
    ],
)
def test_upload_infers_the_content_type_from_the_file_name(name: str, content_type: str) -> None:
    server = serve(STORE)
    client_for(server).citation_check_documents.upload(b"data", filename=name)
    assert server.requests[0].multipart()[0]["content_type"] == content_type
    assert server.requests[0].multipart()[0]["filename"] == name


def test_upload_reads_a_path_and_takes_its_name(tmp_path: Path) -> None:
    path = tmp_path / "schriftsatz.pdf"
    path.write_bytes(b"%PDF-1.7 hello")
    server = serve(STORE, STORE)
    client = client_for(server)
    client.citation_check_documents.upload(path)
    client.citation_check_documents.upload(str(path), content_type="application/x-custom")
    first, second = server.requests
    assert b"%PDF-1.7 hello" in first.body
    assert first.multipart() == [
        {"name": "file", "filename": "schriftsatz.pdf", "content_type": "application/pdf"}
    ]
    assert second.multipart()[0]["content_type"] == "application/x-custom"


def test_upload_takes_the_name_of_a_named_file_object(tmp_path: Path) -> None:
    path = tmp_path / "memo.md"
    path.write_bytes(b"# memo")
    server = serve(STORE)
    with path.open("rb") as handle:
        client_for(server).citation_check_documents.upload(handle)
    assert server.requests[0].multipart()[0]["filename"] == "memo.md"
    assert server.requests[0].multipart()[0]["content_type"] == "text/markdown"


def test_upload_needs_a_filename_for_bytes() -> None:
    server = serve()
    with pytest.raises(ValidationError) as caught:
        client_for(server).citation_check_documents.upload(io.BytesIO(b"x"))
    assert caught.value.code == "client_validation"
    assert server.requests == []


def test_async_upload_reads_a_path(tmp_path: Path) -> None:
    path = tmp_path / "a.docx"
    path.write_bytes(b"PK")

    async def go() -> MockServer:
        server = serve(STORE)
        http = httpx2.AsyncClient(transport=server.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            await client.citation_check_documents.upload(path)
        return server

    server = asyncio.run(go())
    assert server.requests[0].multipart()[0]["filename"] == "a.docx"


def test_get_escape_hatch_returns_a_response_and_retries() -> None:
    slow = {"status": 429, "headers": {"retry-after": "1"}, "body_text": "slow"}
    server = serve(slow, COVERAGE)
    slept: list[float] = []
    client = client_for(server, sleep=slept.append)
    response = client.get("/corpus/coverage", {"top": 3, "branch": None, "ids": ["a", "b"]})
    assert slept == [1.0]
    assert server.requests[0].path == "/corpus/coverage"
    assert server.requests[0].query_map() == {"top": "3", "ids[]": ["a", "b"]}
    assert response.meta.status == 200
    assert response.credits.cost == 0
    assert "total_decisions" in response.extra
    assert response.raw["courts_total"] == response.extra["courts_total"]


def test_post_escape_hatch_sends_json_and_is_not_retried_after_a_dropped_connection() -> None:
    server = serve({"drop_connection": True}, COVERAGE)
    client = client_for(server)
    with pytest.raises(klaracase.TransportError):
        client.post("/datapackages", {"ids": ["a"]}, extra_headers={"X-A": "1"})
    assert len(server.requests) == 1
    assert server.requests[0].json() == {"ids": ["a"]}
    assert server.requests[0].method == "POST"


def test_escape_hatch_paths_must_start_with_a_slash() -> None:
    with pytest.raises(ValidationError):
        client_for(serve()).get("corpus/coverage")


def test_the_async_escape_hatches_work() -> None:
    async def go() -> None:
        server = serve(COVERAGE, COVERAGE)
        http = httpx2.AsyncClient(transport=server.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            got = await client.get("/corpus/coverage")
            posted = await client.post("/datapackages", {"ids": []})
        assert got.meta.status == posted.meta.status == 200
        assert [r.method for r in server.requests] == ["GET", "POST"]

    asyncio.run(go())
