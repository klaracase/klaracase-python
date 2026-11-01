"""Page iterators and create_from_file, sync and async."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import AsyncKlaracase, Klaracase
from tests.mock_server import MockServer

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = FIXTURES / "examples"
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"


def example(name: str) -> dict[str, Any]:
    body = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def ok(body: dict[str, Any], status: int = 200) -> dict[str, Any]:
    return {"status": status, "headers": {}, "body": body}


def serve(*responses: dict[str, Any], repeat: bool = False) -> MockServer:
    return MockServer(
        responses=list(responses),
        base_dir=FIXTURES / "conformance" / "cases",
        repeat_last=repeat,
    )


def client_for(server: MockServer) -> Klaracase:
    http = httpx2.Client(transport=server.transport())
    return Klaracase(TOKEN, base_url=BASE, http_client=http, sleep=lambda _s: None)


def pages_seen(server: MockServer) -> list[str | list[str]]:
    return [r.query_map().get("page", "-") for r in server.requests]


SEARCH_PAGE = example("decisions.search")
EMPTY_SEARCH = {**copy.deepcopy(SEARCH_PAGE), "results": []}


def test_iter_pages_stops_at_an_empty_page_and_does_not_yield_it() -> None:
    server = serve(ok(SEARCH_PAGE), ok(SEARCH_PAGE), ok(EMPTY_SEARCH))
    pages = list(client_for(server).decisions.iter_pages("Untreue", max_pages=5, court="BGH"))
    assert len(pages) == 2
    assert pages_seen(server) == ["1", "2", "3"]
    assert all(r.query_map()["court"] == "BGH" for r in server.requests)
    assert all(isinstance(p, klaracase.DecisionSearch) for p in pages)


def test_iter_pages_stops_at_max_pages() -> None:
    server = serve(ok(SEARCH_PAGE), repeat=True)
    pages = list(client_for(server).decisions.iter_pages("Untreue", max_pages=2))
    assert len(pages) == 2
    assert len(server.requests) == 2


def test_iter_pages_caps_at_ten_pages() -> None:
    server = serve(ok(SEARCH_PAGE), repeat=True)
    list(client_for(server).decisions.iter_pages("Untreue", max_pages=500))
    assert len(server.requests) == 10


def test_iter_pages_is_lazy() -> None:
    server = serve(ok(SEARCH_PAGE), repeat=True)
    iterator = client_for(server).decisions.iter_pages("Untreue", max_pages=3)
    assert server.requests == []
    next(iterator)
    assert len(server.requests) == 1


def test_max_pages_is_required_and_checked_at_the_call() -> None:
    server = serve()
    decisions = client_for(server).decisions
    with pytest.raises(TypeError):
        decisions.iter_pages("x")  # type: ignore[call-arg]
    for bad in (0, -1, True):
        with pytest.raises(klaracase.ValidationError):
            decisions.iter_pages("x", max_pages=bad)
    with pytest.raises(klaracase.ValidationError):
        decisions.iter_pages("x", max_pages=2, page=2)  # type: ignore[call-arg]
    assert server.requests == []


CITATIONS = example("decisions.citations")
EMPTY_CITATIONS = {**copy.deepcopy(CITATIONS), "references": [], "referenced_by": []}


def with_more(more: bool) -> dict[str, Any]:
    body = copy.deepcopy(CITATIONS)
    body["pagination"]["has_more_references"] = more
    body["pagination"]["has_more_referenced_by"] = more
    return body


def test_iter_citation_pages_stops_on_an_empty_page() -> None:
    server = serve(ok(with_more(True)), ok(with_more(True)), ok(EMPTY_CITATIONS))
    client = client_for(server)
    pages = list(client.decisions.iter_citation_pages("1 StR 185/01", max_pages=9, depth=1))
    assert len(pages) == 2
    assert pages_seen(server) == ["1", "2", "3"]
    assert server.requests[0].path == "/decisions/1%20StR%20185%2F01/citations"


def test_iter_citation_pages_stops_when_pagination_says_no_more() -> None:
    server = serve(ok(with_more(True)), ok(with_more(False)), ok(with_more(True)))
    pages = list(client_for(server).decisions.iter_citation_pages("x", max_pages=9))
    assert len(pages) == 2
    assert len(server.requests) == 2


def test_iter_citation_pages_caps_at_twenty_pages() -> None:
    server = serve(ok(with_more(True)), repeat=True)
    list(client_for(server).decisions.iter_citation_pages("x", max_pages=999))
    assert len(server.requests) == 20


def test_the_async_iterators() -> None:
    async def go() -> None:
        search = serve(ok(SEARCH_PAGE), ok(EMPTY_SEARCH))
        graph = serve(ok(with_more(True)), ok(with_more(False)))
        http = httpx2.AsyncClient(transport=search.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            found = [p async for p in client.decisions.iter_pages("q", max_pages=4)]
        assert len(found) == 1
        assert len(search.requests) == 2
        http2 = httpx2.AsyncClient(transport=graph.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http2) as client:
            walked = [p async for p in client.decisions.iter_citation_pages("x", max_pages=4)]
            assert len(walked) == 2
            with pytest.raises(klaracase.ValidationError):
                client.decisions.iter_pages("q", max_pages=0)

    asyncio.run(go())


UPLOADED = ok(example("citation-check-documents.store"), 202)
READY = ok(example("citation-check-documents.show"))
EXTRACTING = ok({**example("citation-check-documents.show"), "status": "extracting"})
FAILED = ok(
    {**example("citation-check-documents.show"), "status": "failed", "error_code": "encrypted_pdf"}
)
CHECK = ok(example("citation-checks.store"))


def test_create_from_file_uploads_waits_and_checks(tmp_path: Path) -> None:
    path = tmp_path / "schriftsatz.pdf"
    path.write_bytes(b"%PDF-1.7 hello")
    server = serve(UPLOADED, EXTRACTING, READY, CHECK)
    slept: list[float] = []
    http = httpx2.Client(transport=server.transport())
    client = Klaracase(TOKEN, base_url=BASE, http_client=http, sleep=slept.append)
    run = client.citation_checks.create_from_file(
        path, reference_date="2026-10-01", poll_interval=0.5
    )
    assert [(r.method, r.path) for r in server.requests] == [
        ("POST", "/citation-check-documents"),
        ("GET", "/citation-check-documents/0193b0c6-3c4d-7e5f-8a60-7c8d9e0f1a2b"),
        ("GET", "/citation-check-documents/0193b0c6-3c4d-7e5f-8a60-7c8d9e0f1a2b"),
        ("POST", "/citation-checks"),
    ]
    assert server.requests[3].json() == {
        "document_id": "0193b0c6-3c4d-7e5f-8a60-7c8d9e0f1a2b",
        "reference_date": "2026-10-01",
    }
    assert slept == [0.5]
    assert run.status == "complete"


def test_create_from_file_raises_when_the_extraction_fails() -> None:
    server = serve(UPLOADED, FAILED)
    with pytest.raises(klaracase.DocumentFailedError) as caught:
        client_for(server).citation_checks.create_from_file(b"x", filename="a.pdf")
    assert caught.value.error_code == "encrypted_pdf"
    assert len(server.requests) == 2


def test_create_from_file_needs_a_filename_for_bytes() -> None:
    with pytest.raises(klaracase.ValidationError):
        client_for(serve()).citation_checks.create_from_file(b"x")


def test_create_from_file_async(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_bytes(b"# x")

    async def go() -> MockServer:
        server = serve(UPLOADED, READY, CHECK)
        http = httpx2.AsyncClient(transport=server.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            run = await client.citation_checks.create_from_file(path)
            assert run.id
        return server

    server = asyncio.run(go())
    assert server.requests[0].multipart()[0]["content_type"] == "text/markdown"
    assert server.requests[-1].path == "/citation-checks"
