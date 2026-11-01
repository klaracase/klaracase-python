"""A local stand-in for the Klaracase API, so the examples run with no token and no network.

It replays the example bodies of the API contract (``tests/fixtures/examples``). The figures in
them are illustrative. To use the real API, build ``Klaracase()`` with a token instead of
``mock_client()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import httpx2

from klaracase import Klaracase

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
RELEASE = "0.95.0"


def _example(name: str) -> bytes:
    return (FIXTURES / "examples" / f"{name}.json").read_bytes()


def _not_found(what: str, value: str) -> httpx2.Response:
    problem = {
        "type": "https://klaracase.de/docs/api/errors#not_found",
        "title": "Not Found",
        "status": 404,
        "detail": f"No {what} matches {value!r} in the corpus.",
        "code": "not_found",
    }
    headers = {"content-type": "application/problem+json", "x-klaracase-api-release": RELEASE}
    return httpx2.Response(404, content=json.dumps(problem).encode(), headers=headers)


def _answer(name: str, status: int = 200) -> httpx2.Response:
    headers = {"content-type": "application/json", "x-klaracase-api-release": RELEASE}
    return httpx2.Response(status, content=_example(name), headers=headers)


def _handle(request: httpx2.Request) -> httpx2.Response:
    raw = request.url.raw_path.decode("ascii").partition("?")[0]
    parts = [unquote(part) for part in raw.removeprefix("/api/v1/").split("/")]
    route = (request.method, parts[0], len(parts))
    if route == ("GET", "decisions", 2) and parts[1] == "search":
        return _answer("decisions.search")
    if route == ("GET", "decisions", 2):
        if parts[1] == "VIII ZR 999/99":
            return _not_found("decision", parts[1])
        return _answer("decisions.show")
    if route == ("GET", "decisions", 3):
        return _answer("decisions.citations")
    if route == ("GET", "norms", 2):
        return _answer("norms.show") if parts[1] == "§ 535 BGB" else _not_found("norm", parts[1])
    if route == ("GET", "search", 1):
        return _answer("search")
    if route == ("POST", "datapackages", 1):
        return _answer("datapackages.store")
    if route == ("POST", "citation-checks", 1):
        return _answer("citation-checks.store")
    if route == ("GET", "citation-checks", 2):
        return _answer("citation-checks.show")
    if route == ("POST", "citation-check-documents", 1):
        return _answer("citation-check-documents.store", 202)
    if route == ("GET", "citation-check-documents", 2):
        return _answer("citation-check-documents.show")
    if route == ("GET", "corpus", 2) and parts[1] == "coverage":
        return _answer("corpus.coverage")
    if route == ("GET", "corpus", 3) and parts[1] == "facets":
        return _answer("corpus.facets")
    return _not_found("route", raw)


def mock_client() -> Klaracase:
    """A sync client whose HTTP transport is the local mock."""
    http = httpx2.Client(transport=httpx2.MockTransport(_handle))
    return Klaracase("klc_your_token_here", http_client=http)
