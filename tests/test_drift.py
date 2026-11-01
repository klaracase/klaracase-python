"""Drift guards: the typed model must cover every key the contract and its examples carry.

A key the model does not list lands in ``extra``. These tests walk every decoded object at every
depth and fail when any ``extra`` is non-empty, so a new key in a body is a red test, not a silent
miss. The walker itself is checked by injecting a key (it must fail to be trusted).
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import typing
from pathlib import Path
from typing import Any

import pytest

import klaracase
from klaracase import types as klaracase_types
from klaracase.types import Response

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = FIXTURES / "examples"
BODIES = FIXTURES / "conformance" / "bodies"
CONTRACT = (FIXTURES / "contract" / "CONTRACT.md").read_text(encoding="utf-8")
SKIPPED_BODY = "decisions.search.future_key.json"

EXAMPLE_CLASSES: dict[str, type[Response]] = {
    "citation-check-documents.show.json": klaracase.CitationCheckDocument,
    "citation-check-documents.store.json": klaracase.CitationCheckDocument,
    "citation-checks.show.json": klaracase.CitationCheck,
    "citation-checks.store.json": klaracase.CitationCheck,
    "corpus.coverage.json": klaracase.CorpusCoverage,
    "corpus.facets.json": klaracase.CorpusFacets,
    "datapackages.store.json": klaracase.Datapackage,
    "decisions.citations.json": klaracase.DecisionCitations,
    "decisions.search.json": klaracase.DecisionSearch,
    "decisions.show.json": klaracase.Decision,
    "norms.show.json": klaracase.Norm,
    "search.json": klaracase.CrossTypeSearch,
}

BODY_CLASSES: dict[str, type[Response]] = {
    "corpus.coverage.not_metered.json": klaracase.CorpusCoverage,
    "corpus.facets.cited_norms.json": klaracase.CorpusFacets,
    "documents.extracting.json": klaracase.CitationCheckDocument,
    "documents.failed.encrypted_pdf.json": klaracase.CitationCheckDocument,
    "documents.ocr_pending.json": klaracase.CitationCheckDocument,
    "documents.ready.json": klaracase.CitationCheckDocument,
    "documents.uploaded.json": klaracase.CitationCheckDocument,
    "norms.show.dsgvo.json": klaracase.Norm,
}

CONTRACT_CLASSES: dict[str, type[Response]] = {
    "POST /citation-checks": klaracase.CitationCheck,
    "GET /citation-checks/{run}": klaracase.CitationCheck,
    "POST /citation-check-documents": klaracase.CitationCheckDocument,
    "GET /citation-check-documents/{document}": klaracase.CitationCheckDocument,
    "GET /decisions/{id}/citations": klaracase.DecisionCitations,
    "GET /corpus/coverage": klaracase.CorpusCoverage,
    "GET /corpus/facets/{field}": klaracase.CorpusFacets,
    "POST /datapackages": klaracase.Datapackage,
    "GET /decisions/{id}": klaracase.Decision,
    "GET /norms/{reference}": klaracase.Norm,
    "GET /decisions/search": klaracase.DecisionSearch,
    "GET /search": klaracase.CrossTypeSearch,
}


def read(path: Path) -> dict[str, Any]:
    body = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def contract_blocks() -> dict[str, dict[str, Any]]:
    """The first JSON block of each operation section of ``CONTRACT.md``."""
    blocks: dict[str, dict[str, Any]] = {}
    for section in re.split(r"^## ", CONTRACT, flags=re.MULTILINE)[1:]:
        heading = section.split("\n", 1)[0].strip()
        if not re.match(r"(GET|POST) /", heading):
            continue
        match = re.search(r"```json\n(.*?)```", section, flags=re.DOTALL)
        assert match, f"no JSON block under {heading}"
        blocks[heading] = json.loads(match.group(1))
    return blocks


def unmodelled(value: Any, path: str = "") -> list[str]:
    """Return the path of every object whose ``extra`` is not empty, at any depth."""
    found: list[str] = []
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        extra = getattr(value, "extra", None)
        if extra:
            found.append(f"{path or '<root>'}: {sorted(extra)}")
        for item in dataclasses.fields(value):
            if item.name in {"extra", "raw", "meta"}:
                continue
            child = f"{path}.{item.name}" if path else item.name
            found += unmodelled(getattr(value, item.name), child)
    elif isinstance(value, list):
        for index, item in enumerate(typing.cast("list[Any]", value)):
            found += unmodelled(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in typing.cast("dict[str, Any]", value).items():
            found += unmodelled(item, f"{path}[{key!r}]")
    return found


def enum_violations(value: Any, path: str = "") -> list[str]:
    """Return every string that a ``Literal[...] | str`` field holds outside its Literal."""
    found: list[str] = []
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        hints = typing.get_type_hints(type(value))
        for item in dataclasses.fields(value):
            if item.name in {"extra", "raw", "meta"}:
                continue
            child = f"{path}.{item.name}" if path else item.name
            current = getattr(value, item.name)
            members = {
                member
                for arg in typing.get_args(hints[item.name])
                if typing.get_origin(arg) is typing.Literal
                for member in typing.get_args(arg)
            }
            if members and isinstance(current, str) and current not in members:
                found.append(f"{child}={current!r}")
            found += enum_violations(current, child)
    elif isinstance(value, list):
        for index, item in enumerate(typing.cast("list[Any]", value)):
            found += enum_violations(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in typing.cast("dict[str, Any]", value).items():
            found += enum_violations(item, f"{path}[{key!r}]")
    return found


def sources() -> list[tuple[str, type[Response], dict[str, Any]]]:
    items: list[tuple[str, type[Response], dict[str, Any]]] = []
    for name, cls in EXAMPLE_CLASSES.items():
        items.append((f"example:{name}", cls, read(EXAMPLES / name)))
    for name, cls in BODY_CLASSES.items():
        items.append((f"body:{name}", cls, read(BODIES / name)))
    for heading, body in contract_blocks().items():
        items.append((f"contract:{heading}", CONTRACT_CLASSES[heading], body))
    return items


SOURCES = sources()
IDS = [source[0] for source in SOURCES]


@pytest.mark.parametrize(("label", "cls", "body"), SOURCES, ids=IDS)
def test_no_extra_at_any_depth(label: str, cls: type[Response], body: dict[str, Any]) -> None:
    assert unmodelled(cls.from_dict(body)) == []


@pytest.mark.parametrize(("label", "cls", "body"), SOURCES, ids=IDS)
def test_to_dict_returns_the_body(label: str, cls: type[Response], body: dict[str, Any]) -> None:
    assert cls.from_dict(copy.deepcopy(body)).to_dict() == body


# CONTRACT.md still shows the retired verdict "verified" (the closed vocabulary says
# "verified_corpus"; see facts.md, defects seen). Nothing else may be outside its Literal.
STALE_CONTRACT_VERDICT = "'verified'"


@pytest.mark.parametrize(("label", "cls", "body"), SOURCES, ids=IDS)
def test_every_enum_value_is_a_member_of_its_literal(
    label: str, cls: type[Response], body: dict[str, Any]
) -> None:
    violations = enum_violations(cls.from_dict(body))
    if label.startswith("contract:"):
        violations = [v for v in violations if not v.endswith(f"={STALE_CONTRACT_VERDICT}")]
    assert violations == []


def test_the_walker_reports_a_nested_unknown_key() -> None:
    body = read(EXAMPLES / "citation-checks.show.json")
    assert unmodelled(klaracase.CitationCheck.from_dict(body)) == []
    body["findings"][0]["evidence"]["a_key_from_the_future"] = 1
    body["extraction"]["another_one"] = []
    found = unmodelled(klaracase.CitationCheck.from_dict(body))
    assert found == [
        "extraction: ['another_one']",
        "findings[0].evidence: ['a_key_from_the_future']",
    ]


def test_the_walker_reports_a_key_inside_a_mapping_of_objects() -> None:
    body = read(EXAMPLES / "corpus.facets.json")
    body["values"]["BGH"]["new_count_key"] = 1
    assert unmodelled(klaracase.CorpusFacets.from_dict(body)) == [
        "values['BGH']: ['new_count_key']"
    ]


def test_the_deliberate_future_key_body_is_reported() -> None:
    body = read(BODIES / SKIPPED_BODY)
    found = unmodelled(klaracase.DecisionSearch.from_dict(body))
    assert found == [
        "<root>: ['another_future_key', 'future_key']",
        "results[0]: ['future_result_key']",
    ]


def test_the_enum_check_reports_a_value_outside_its_literal() -> None:
    body = read(EXAMPLES / "citation-checks.show.json")
    body["findings"][0]["verdict"] = "verified"
    found = enum_violations(klaracase.CitationCheck.from_dict(body))
    assert found == ["findings[0].verdict='verified'"]


def test_every_example_file_maps_to_a_class() -> None:
    on_disk = {path.name for path in EXAMPLES.glob("*.json")}
    assert on_disk == set(EXAMPLE_CLASSES)


def test_every_conformance_body_is_mapped_or_skipped() -> None:
    on_disk = {path.name for path in BODIES.glob("*.json")}
    assert on_disk - {SKIPPED_BODY} == set(BODY_CLASSES)


def test_every_operation_section_of_the_contract_is_mapped() -> None:
    assert set(contract_blocks()) == set(CONTRACT_CLASSES)


def test_every_response_class_has_an_example() -> None:
    declared = {
        cls
        for cls in vars(klaracase_types).values()
        if isinstance(cls, type) and issubclass(cls, Response) and cls is not Response
    }
    assert declared == set(EXAMPLE_CLASSES.values())
