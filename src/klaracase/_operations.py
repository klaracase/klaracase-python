"""Builders for the twelve API operations.

Each function validates its arguments, encodes path parameters and returns an ``Operation``.
Sync and async resources both call these, so the wire format is written once.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, BinaryIO

from ._core import Operation, client_validation_error, query_pairs, quote_segment
from .types import (
    Branch,
    CitationCheck,
    CitationCheckDocument,
    CitationDepth,
    CitationDirection,
    CitedStatute,
    CorpusCoverage,
    CorpusFacets,
    CrossTypeSearch,
    Datapackage,
    Decision,
    DecisionCitations,
    DecisionSearch,
    DocumentType,
    FacetField,
    FacetType,
    Norm,
    NormJurisdiction,
    SearchJurisdiction,
    SearchMode,
)


def _string_list(name: str, value: Sequence[str] | None) -> Sequence[str] | None:
    if isinstance(value, str):
        raise client_validation_error(f"{name} must be a list of strings, not one string.")
    return value


def decisions_search(
    query: str,
    *,
    court: str | None,
    branch: Branch | None,
    document_type: DocumentType | None,
    cited_norm: str | None,
    cited_statutes: Sequence[CitedStatute] | None,
    date_from: str | None,
    date_to: str | None,
    mode: SearchMode | None,
    limit: int | None,
    page: int | None,
    bridge: bool | None,
) -> Operation[DecisionSearch]:
    params = {
        "query": query,
        "court": court,
        "branch": branch,
        "document_type": document_type,
        "cited_norm": cited_norm,
        "cited_statutes": _string_list("cited_statutes", cited_statutes),
        "date_from": date_from,
        "date_to": date_to,
        "mode": mode,
        "limit": limit,
        "page": page,
        "bridge": bridge,
    }
    return Operation("GET", "/decisions/search", DecisionSearch, query=query_pairs(params))


def cross_type_search(
    query: str,
    *,
    jurisdiction: SearchJurisdiction | None,
    court: str | None,
    branch: Branch | None,
    date_from: str | None,
    date_to: str | None,
    mode: SearchMode | None,
    document_type: DocumentType | None,
    cited_norm: str | None,
    cited_statutes: Sequence[CitedStatute] | None,
    limit: int | None,
    bridge: bool | None,
) -> Operation[CrossTypeSearch]:
    params = {
        "query": query,
        "jurisdiction": jurisdiction,
        "court": court,
        "branch": branch,
        "date_from": date_from,
        "date_to": date_to,
        "mode": mode,
        "document_type": document_type,
        "cited_norm": cited_norm,
        "cited_statutes": _string_list("cited_statutes", cited_statutes),
        "limit": limit,
        "bridge": bridge,
    }
    return Operation("GET", "/search", CrossTypeSearch, query=query_pairs(params))


def decision_get(
    id: str,
    *,
    max_chars: int | None,
    rn_from: int | None,
    rn_to: int | None,
    section: str | None,
    court: str | None,
    date: str | None,
) -> Operation[Decision]:
    params = {
        "max_chars": max_chars,
        "rn_from": rn_from,
        "rn_to": rn_to,
        "section": section,
        "court": court,
        "date": date,
    }
    return Operation("GET", f"/decisions/{quote_segment(id)}", Decision, query=query_pairs(params))


def decision_citations(
    id: str,
    *,
    direction: CitationDirection | None,
    depth: CitationDepth | None,
    court: str | None,
    date: str | None,
    page: int | None,
) -> Operation[DecisionCitations]:
    params = {
        "direction": direction,
        "depth": depth,
        "court": court,
        "date": date,
        "page": page,
    }
    return Operation(
        "GET",
        f"/decisions/{quote_segment(id)}/citations",
        DecisionCitations,
        query=query_pairs(params),
    )


def norm_get(reference: str, *, jurisdiction: NormJurisdiction | None) -> Operation[Norm]:
    return Operation(
        "GET",
        f"/norms/{quote_segment(reference)}",
        Norm,
        query=query_pairs({"jurisdiction": jurisdiction}),
    )


def datapackage_create(
    ids: Sequence[str],
    *,
    include_citations: bool | None,
    full_text: bool | None,
    max_chars: int | None,
) -> Operation[Datapackage]:
    if isinstance(ids, str):
        raise client_validation_error("ids must be a list of decision ids, not one string.")
    body: dict[str, Any] = {"ids": list(ids)}
    for name, value in (
        ("include_citations", include_citations),
        ("full_text", full_text),
        ("max_chars", max_chars),
    ):
        if value is not None:
            body[name] = value
    return Operation("POST", "/datapackages", Datapackage, json_body=body)


def citation_check_create(
    *,
    text: str | None,
    document_id: str | None,
    reference_date: str | None,
) -> Operation[CitationCheck]:
    if (text is None) == (document_id is None):
        raise client_validation_error("Pass exactly one of text or document_id.")
    body: dict[str, Any] = {}
    if text is not None:
        body["text"] = text
    if document_id is not None:
        body["document_id"] = document_id
    if reference_date is not None:
        body["reference_date"] = reference_date
    return Operation("POST", "/citation-checks", CitationCheck, json_body=body)


def citation_check_get(run_id: str) -> Operation[CitationCheck]:
    return Operation("GET", f"/citation-checks/{quote_segment(run_id)}", CitationCheck)


def document_upload(
    data: bytes, *, filename: str, content_type: str
) -> Operation[CitationCheckDocument]:
    return Operation(
        "POST",
        "/citation-check-documents",
        CitationCheckDocument,
        files={"file": (filename, data, content_type)},
    )


def document_get(document_id: str) -> Operation[CitationCheckDocument]:
    return Operation(
        "GET",
        f"/citation-check-documents/{quote_segment(document_id)}",
        CitationCheckDocument,
    )


def corpus_coverage(*, branch: Branch | None, top: int | None) -> Operation[CorpusCoverage]:
    return Operation(
        "GET",
        "/corpus/coverage",
        CorpusCoverage,
        query=query_pairs({"branch": branch, "top": top}),
    )


def corpus_facets(
    field: FacetField,
    *,
    type: FacetType | None,
    norm: str | None,
    prefix: str | None,
) -> Operation[CorpusFacets]:
    return Operation(
        "GET",
        f"/corpus/facets/{quote_segment(field)}",
        CorpusFacets,
        query=query_pairs({"type": type, "norm": norm, "prefix": prefix}),
    )


def read_file(file: bytes | bytearray | memoryview | BinaryIO) -> bytes:
    """Return the upload as bytes. A file object is read once, so a retry sends the same bytes."""
    if isinstance(file, (bytes, bytearray, memoryview)):
        return bytes(file)
    data = file.read()
    if not isinstance(data, bytes):
        raise client_validation_error("file must be bytes or a binary file object.")
    return data
