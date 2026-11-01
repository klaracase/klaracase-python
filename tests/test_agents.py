"""The agents module: tool definitions that cannot drift from the client, and the dispatcher."""

from __future__ import annotations

import asyncio
import inspect
import json
import typing
from pathlib import Path
from typing import Any

import httpx2
import pytest

import klaracase
from klaracase import AsyncKlaracase, ConfigurationError, Klaracase
from klaracase.agents import TOOL_NAMES, adispatch, dispatch, tool_definitions
from tests.mock_server import MockServer
from tests.test_copy_lint import find_forbidden

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "http://127.0.0.1:1/api/v1"
TOKEN = "klc_your_token_here"
OPTION_NAMES = {"timeout", "extra_headers", "extra_query"}
TARGETS = {
    "search_decisions": "decisions.search",
    "cross_type_search": "search",
    "get_decision": "decisions.get",
    "get_norm": "norms.get",
    "check_citations": "citation_checks.create",
}


def serve(*responses: dict[str, Any]) -> MockServer:
    return MockServer(responses=list(responses), base_dir=FIXTURES / "conformance" / "cases")


def example(name: str, status: int = 200) -> dict[str, Any]:
    return {"status": status, "headers": {}, "body_file": f"../../examples/{name}.json"}


def client_for(server: MockServer) -> Klaracase:
    http = httpx2.Client(transport=server.transport())
    return Klaracase(TOKEN, base_url=BASE, http_client=http, sleep=lambda _s: None)


def method_of(client: Klaracase | AsyncKlaracase, target: str) -> Any:
    obj: Any = client
    for part in target.split("."):
        obj = getattr(obj, part)
    return obj


def test_all_five_tools_in_a_fixed_order() -> None:
    assert [d["name"] for d in tool_definitions()] == [
        "search_decisions",
        "cross_type_search",
        "get_decision",
        "get_norm",
        "check_citations",
    ]
    assert tuple(TARGETS) == TOOL_NAMES


def test_names_pick_and_order_the_tools() -> None:
    picked = tool_definitions(["get_norm", "search_decisions"])
    assert [d["name"] for d in picked] == ["get_norm", "search_decisions"]


def test_the_three_formats() -> None:
    schema = tool_definitions(["get_norm"])[0]["parameters"]
    assert tool_definitions(["get_norm"], format="json_schema")[0].keys() == {
        "name",
        "description",
        "parameters",
    }
    anthropic = tool_definitions(["get_norm"], format="anthropic")[0]
    assert anthropic.keys() == {"name", "description", "input_schema"}
    assert anthropic["input_schema"] == schema
    openai = tool_definitions(["get_norm"], format="openai")[0]
    assert openai["type"] == "function"
    assert openai["function"]["parameters"] == schema
    assert openai["function"]["name"] == "get_norm"
    assert schema["type"] == "object"
    assert schema["required"] == ["reference"]


def test_unknown_names_and_formats_are_configuration_errors() -> None:
    with pytest.raises(ConfigurationError):
        tool_definitions(["get_citation_graph"])
    with pytest.raises(ConfigurationError):
        tool_definitions(format="yaml")  # type: ignore[arg-type]


def test_definitions_are_copies() -> None:
    first = tool_definitions()
    first[0]["parameters"]["properties"].clear()
    assert tool_definitions()[0]["parameters"]["properties"]


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_schema_properties_equal_the_method_keyword_parameters(name: str) -> None:
    definition = tool_definitions([name])[0]
    properties = set(definition["parameters"]["properties"])
    for client in (Klaracase(TOKEN), AsyncKlaracase(TOKEN)):
        signature = inspect.signature(method_of(client, TARGETS[name]))
        parameters = {p for p in signature.parameters if p not in OPTION_NAMES}
        assert properties == parameters, name
        required = {
            p.name
            for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty and p.name not in OPTION_NAMES
        }
        assert required <= set(definition["parameters"].get("required", []))
        assert set(definition["parameters"].get("required", [])) <= properties


def test_enums_come_from_the_request_literals() -> None:
    props = tool_definitions(["search_decisions"])[0]["parameters"]["properties"]
    assert props["branch"]["enum"] == list(typing.get_args(klaracase.Branch))
    assert props["document_type"]["enum"] == list(typing.get_args(klaracase.DocumentType))
    assert props["cited_statutes"]["items"]["enum"] == list(typing.get_args(klaracase.CitedStatute))
    assert props["mode"]["enum"] == ["keyword", "semantic", "hybrid"]


def test_descriptions_are_plain_and_pass_the_copy_lint() -> None:
    for definition in tool_definitions():
        assert find_forbidden(json.dumps(definition)) == [], definition["name"]
        assert "—" not in definition["description"]
        assert definition["description"].endswith(".")
    check = tool_definitions(["check_citations"])[0]["description"]
    assert "not found in the corpus" in check


def test_dispatch_returns_compact_json_without_envelope_noise() -> None:
    server = serve(example("decisions.search"))
    text = dispatch(client_for(server), "search_decisions", {"query": "Untreue", "court": "BGH"})
    body = json.loads(text)
    assert text == json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    assert body["results"][0]["aktenzeichen"] == "1 StR 185/01"
    assert "api_version" not in body
    assert "changelog_url" not in body
    assert "credits" in body
    assert server.requests[0].query_map() == {"query": "Untreue", "court": "BGH"}


def test_dispatch_keeps_umlauts_unescaped() -> None:
    server = serve(example("norms.show"))
    text = dispatch(client_for(server), "get_norm", {"reference": "§ 535 BGB"})
    assert "\\u" not in text
    assert "§" in text


def test_get_decision_defaults_max_chars_to_4000_and_respects_a_choice() -> None:
    server = serve(example("decisions.show"), example("decisions.show"))
    client = client_for(server)
    dispatch(client, "get_decision", {"id": "1 StR 185/01"})
    dispatch(client, "get_decision", {"id": "1 StR 185/01", "max_chars": 9000, "section": "Gründe"})
    assert server.requests[0].query_map() == {"max_chars": "4000"}
    assert server.requests[1].query_map() == {"max_chars": "9000", "section": "Gründe"}


def test_check_citations_is_reduced() -> None:
    server = serve(example("citation-checks.store"))
    text = dispatch(client_for(server), "check_citations", {"text": "x" * 60})
    body = json.loads(text)
    assert list(body) == ["id", "status", "verdict_counts", "unique_citations", "findings"]
    assert body["verdict_counts"] == {"verified_corpus": 1, "not_found": 1}
    assert body["status"] == "complete"
    assert len(body["unique_citations"]) == 2
    for finding in body["findings"]:
        assert list(finding) == [
            "id",
            "canonical",
            "verdict",
            "raw_text",
            "start_offset",
            "end_offset",
        ]
    assert "evidence" not in text
    assert server.requests[0].json() == {"text": "x" * 60}


def test_dispatch_accepts_json_text_arguments() -> None:
    server = serve(example("norms.show"))
    text = dispatch(client_for(server), "get_norm", '{"reference": "§ 535 BGB"}')
    assert json.loads(text)["reference"] == "§ 535 BGB"


def error_of(text: str) -> dict[str, Any]:
    body = json.loads(text)
    assert list(body) == ["error"]
    assert list(body["error"]) == ["code", "detail", "retry_after_seconds"]
    return body["error"]  # type: ignore[no-any-return]


def test_an_api_error_becomes_an_error_object() -> None:
    server = serve(
        {"status": 402, "headers": {}, "body_file": "../problems/insufficient_credits.json"}
    )
    error = error_of(dispatch(client_for(server), "get_norm", {"reference": "§ 1 BGB"}))
    assert error["code"] == "insufficient_credits"
    assert error["retry_after_seconds"] is None
    assert error["detail"]


def test_a_rate_limit_error_carries_the_wait() -> None:
    server = serve(
        {"status": 429, "headers": {}, "body_file": "../problems/rate_limited.retry_120s.json"}
    )
    error = error_of(dispatch(client_for(server), "get_norm", {"reference": "§ 1 BGB"}))
    assert error["code"] == "rate_limited"
    assert error["retry_after_seconds"] == 120


def test_a_client_side_refusal_becomes_an_error_object() -> None:
    server = serve()
    error = error_of(
        dispatch(client_for(server), "check_citations", {"text": "x" * 60, "document_id": "d"})
    )
    assert error["code"] == "client_validation"
    assert server.requests == []


@pytest.mark.parametrize(
    ("name", "args", "needle"),
    [
        ("get_citation_graph", {}, "Unknown tool"),
        ("get_norm", {"reference": "§ 1", "nope": 1}, "Unknown argument"),
        ("get_norm", {}, "Missing required"),
        ("get_norm", "{not json", "not valid JSON"),
        ("get_norm", "[1]", "must be a JSON object"),
    ],
)
def test_bad_calls_become_error_objects_without_a_request(
    name: str, args: Any, needle: str
) -> None:
    server = serve()
    error = error_of(dispatch(client_for(server), name, args))
    assert needle in error["detail"]
    assert server.requests == []


def test_adispatch_matches_dispatch() -> None:
    async def go() -> tuple[str, str]:
        server = serve(
            example("norms.show"),
            {"status": 402, "headers": {}, "body_file": "../problems/insufficient_credits.json"},
        )
        http = httpx2.AsyncClient(transport=server.transport())
        async with AsyncKlaracase(TOKEN, base_url=BASE, http_client=http) as client:
            ok = await adispatch(client, "get_norm", {"reference": "§ 535 BGB"})
            err = await adispatch(client, "get_norm", {"reference": "§ 535 BGB"})
        return ok, err

    ok, err = asyncio.run(go())
    assert json.loads(ok)["reference"] == "§ 535 BGB"
    assert error_of(err)["code"] == "insufficient_credits"
