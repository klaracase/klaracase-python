"""Request value types and response types.

Request parameters are typed strictly with ``Literal`` unions. Response values that come from a
closed vocabulary are typed ``Literal | str``: a value the server adds later stays a plain string
and never raises.

Every response class has the same shape:

* one field per documented top-level key, with the value exactly as the API sent it;
* ``extra``: every top-level key this SDK version does not model (the API only adds keys);
* ``meta``: a :class:`ResponseMeta` with the HTTP status, the API release and the duration;
* ``to_dict()``: the parsed body, unchanged. Nothing is renamed, reordered, cleaned or translated.

A documented key that the server did not send reads as ``None``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Any, Literal, Self, TypedDict

__all__ = [
    "Branch",
    "CitationCheck",
    "CitationCheckDocument",
    "CitedStatute",
    "CorpusCoverage",
    "CorpusFacets",
    "Count",
    "Credits",
    "CrossTypeSearch",
    "Datapackage",
    "Decision",
    "DecisionCitations",
    "DecisionSearch",
    "DeprecationNotice",
    "DocumentErrorCode",
    "DocumentStatus",
    "DocumentType",
    "Finding",
    "MatchedDecision",
    "Norm",
    "Response",
    "ResponseMeta",
    "RunStatus",
    "SearchMode",
    "SearchResult",
    "Snippet",
    "UniqueCitation",
    "Verdict",
]

Branch = Literal[
    "ordentlich",
    "verwaltung",
    "sozial",
    "arbeit",
    "finanz",
    "verfassung",
    "patent",
    "unbekannt",
]
"""Gerichtsbarkeit (court branch). It names the court jurisdiction, not the legal subject."""

DocumentType = Literal[
    "Urteil", "Beschluss", "Verfügung", "Sonstige", "Gerichtsbescheid", "Schlussanträge"
]
SearchMode = Literal["keyword", "semantic", "hybrid"]
CitedStatute = Literal[
    "StGB", "StPO", "InsO", "DSGVO", "GDPR", "BDSG", "BauGB", "BBauG", "BauNVO", "StVG", "StVO"
]
CitationDirection = Literal["outgoing", "incoming", "both"]
CitationDepth = Literal[1, 2]
SearchJurisdiction = Literal["DE", "EU", "XI"]
"""Narrows the laws section of the cross-type search."""

NormJurisdiction = Literal["DE", "EU"]
FacetField = Literal[
    "court_name", "court_branch", "document_type", "jurisdiction", "law_type", "cited_norms"
]
FacetType = Literal["decision", "law"]

Verdict = Literal[
    "verified_corpus",
    "verified_external",
    "not_found",
    "out_of_coverage",
    "ambiguous",
    "unverifiable",
    "discrepancy",
]
"""A ``not_found`` verdict means the citation was not found in the corpus. It is not a claim that
the citation is fabricated."""

RunStatus = Literal[
    "pending",
    "gating",
    "extracting",
    "resolving",
    "checking_external",
    "complete",
    "rejected",
    "failed",
]
DocumentStatus = Literal["uploaded", "extracting", "ocr_pending", "ready", "failed"]
DocumentErrorCode = Literal[
    "document_too_long",
    "unsupported_format_pending",
    "corrupted_document",
    "zip_bomb_rejected",
    "encrypted_pdf",
    "scanned_pdf",
    "pdf_text_garbled",
    "extraction_failed",
]

DOCUMENT_TERMINAL_STATUSES = frozenset({"ready", "failed"})


class Count(TypedDict, total=False):
    """A count that can be a lower bound."""

    value: int
    is_floor: bool


class Snippet(TypedDict, total=False):
    text: str
    rn: int | None


class SearchResult(TypedDict, total=False):
    """One decision in ``decisions.search``. Keys the API adds later are still present."""

    id: str
    aktenzeichen: str
    court: str
    date: str
    document_type: str
    title: str
    snippet: str
    snippets: list[Snippet]
    chunk_title: str | None
    rn_range: str | None
    fundstelle: str | None
    fortgeltung_checked: bool
    fortgeltung_note: str
    confidence: str


class MatchedDecision(TypedDict, total=False):
    artifact_id: str
    ecli: str | None
    court: str
    date: str


class Finding(TypedDict, total=False):
    """One citation found in the checked text, with offsets into that text (code points)."""

    id: str
    raw_text: str
    canonical: str
    type: str
    role: str | None
    verdict: Verdict | str
    external_status: str
    start_offset: int
    end_offset: int
    occurrence_index: int
    confidence: str | None
    matched_decision: MatchedDecision | None
    subdivision_check: str
    subdivision_advisory: str | None
    check_scope: dict[str, Any]
    ambiguity_advisory: str | None
    coverage: Any
    coverage_boundary: Any
    coverage_advisory: str | None
    evidence: dict[str, Any]
    disputed_at: str | None


class UniqueCitation(TypedDict, total=False):
    key_basis: str
    target_artifact_id: str | None
    canonical: str
    spellings: list[str]
    occurrences: int
    verdict: Verdict | str
    reference_type: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ResponseMeta:
    """What the transport knows about an answer.

    Attributes:
        status: The HTTP status (200 or 202).
        api_release: The ``X-Klaracase-Api-Release`` header, or ``None`` if it was absent.
        request_duration: Seconds spent on the HTTP exchange that produced this answer.
    """

    status: int
    api_release: str | None
    request_duration: float


@dataclass(slots=True, frozen=True, kw_only=True)
class Credits:
    """The ``credits`` object of an answer. A superadmin answer has ``metered=False`` and nulls."""

    metered: bool | None = None
    cost: int | None = None
    credits_remaining: int | None = None

    @classmethod
    def from_body(cls, value: Any) -> Credits | None:
        if not isinstance(value, dict):
            return None
        return cls(
            metered=value.get("metered"),
            cost=value.get("cost"),
            credits_remaining=value.get("credits_remaining"),
        )


@dataclass(slots=True, frozen=True, kw_only=True)
class DeprecationNotice:
    """The raw ``Deprecation``, ``Sunset`` and ``Link`` header values of an answer."""

    deprecation: str | None
    sunset: str | None
    link: str | None
    method: str
    url: str


@dataclass(slots=True, frozen=True, kw_only=True)
class Response:
    """Base of every response. See the module docstring for the shape."""

    api_version: str | None
    changelog_url: str | None
    credits: Credits | None
    extra: dict[str, Any]
    meta: ResponseMeta
    raw: dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_body(cls, body: dict[str, Any], meta: ResponseMeta) -> Self:
        """Build the response from a parsed JSON body."""
        known = {f.name for f in fields(cls)} - {"extra", "meta", "raw", "credits"}
        values = {name: body.get(name) for name in known}
        extra = {key: value for key, value in body.items() if key not in known | {"credits"}}
        return cls(
            **values,
            credits=Credits.from_body(body.get("credits")),
            extra=extra,
            meta=meta,
            raw=body,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the parsed body unchanged (a deep copy, without ``meta``)."""
        return copy.deepcopy(self.raw)


@dataclass(slots=True, frozen=True, kw_only=True)
class DecisionSearch(Response):
    """Answer of ``GET /decisions/search``."""

    results: list[SearchResult]
    payload_truncated: bool | None
    total_available: Count | None
    total_available_basis: str | None
    candidate_pool: int | None
    pool_exhaustive: bool | None
    truncated: bool | None
    page: int | None
    limit: int | None
    mode: str | None
    frequently_cited_by_results: list[dict[str, Any]]
    query_expansion: dict[str, Any] | None
    top_confidence: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class CrossTypeSearch(Response):
    """Answer of ``GET /search``: ``sections`` holds ``laws`` and ``decisions``."""

    sections: dict[str, list[dict[str, Any]]]
    section_totals: dict[str, dict[str, Any]]
    limit: int | None
    total_available: Count | None
    total_available_basis: str | None
    pool_exhaustive: bool | None
    truncated: bool | None
    mode: str | None
    query_expansion: dict[str, Any] | None
    frequently_cited_by_results: list[dict[str, Any]]
    norms_cited_by_decision_results: list[dict[str, Any]]
    top_confidence: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class Decision(Response):
    """Answer of ``GET /decisions/{id}``."""

    id: str
    aktenzeichen: str | None
    court: str | None
    date: str | None
    jurisdiction: str | None
    metadata: dict[str, Any]
    fortgeltung_checked: bool | None
    fortgeltung_note: str | None
    full_text: str | None
    text_length: int | None
    truncated: bool | None
    rn_source: str | None
    rn_source_note: str | None
    available_sections: list[str]
    available_range: dict[str, Any] | None
    available_range_scope: str | None
    has_rn_anchors: bool | None


@dataclass(slots=True, frozen=True, kw_only=True)
class DecisionCitations(Response):
    """Answer of ``GET /decisions/{id}/citations``."""

    source: dict[str, Any]
    references: list[dict[str, Any]]
    referenced_by: list[dict[str, Any]]
    served_direction: str | None
    served_references_total: int | None
    served_referenced_by_total: int | None
    references_total: int | None
    references_resolved_total: int | None
    referenced_by_total: int | None
    references_unresolved_total: int | None
    references_withheld_reasons: list[Any]
    totals_scope: str | None
    per_direction_cap: int | None
    unresolved_cap: int | None
    node_cap: int | None
    truncated: bool | None
    nodes_omitted: int | None
    payload_truncated: bool | None
    pagination: dict[str, Any] | None
    fortgeltung_checked: bool | None
    fortgeltung_note: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class Norm(Response):
    """Answer of ``GET /norms/{reference}``."""

    reference: str
    requested_reference: str | None
    law: dict[str, Any]
    norm: dict[str, Any]
    requested_qualifiers: list[Any]
    version: dict[str, Any]
    neighbours: dict[str, Any]
    links: dict[str, Any]


@dataclass(slots=True, frozen=True, kw_only=True)
class Datapackage(Response):
    """Answer of ``POST /datapackages``."""

    decisions: list[dict[str, Any]]
    citation_edges: list[dict[str, Any]]
    edge_accounting: list[dict[str, Any]]
    per_source_resolved_target_cap: int | None
    per_source_unresolved_edge_row_cap: int | None
    requested: int | None
    included: int | None
    deduped: int | None
    text_mode: str | None
    max_chars: int | None
    truncated: bool | None
    payload_truncated: bool | None
    assembled_at: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class CitationCheck(Response):
    """A citation check run (``POST /citation-checks`` and ``GET /citation-checks/{run}``).

    ``verdict_counts`` maps a verdict name to a count. ``findings`` carries one entry per
    citation found, with offsets into the text you sent.
    """

    id: str
    status: RunStatus | str
    source: str | None
    progress: dict[str, int]
    verdict_counts: dict[str, int]
    partial: bool | None
    unverified_count: int | None
    reason_counts: list[dict[str, Any]]
    unique_citations: list[UniqueCitation]
    extraction: dict[str, Any]
    notes: list[Any]
    findings_unavailable_reason: str | None
    findings_purged_at: str | None
    findings: list[Finding]
    submitted_at: str | None
    completed_at: str | None
    created_at: str | None
    payload_truncated: bool | None


@dataclass(slots=True, frozen=True, kw_only=True)
class CitationCheckDocument(Response):
    """The receipt of an upload. It never holds the text."""

    id: str
    filename: str | None
    format: str | None
    status: DocumentStatus | str
    char_count: int | None
    page_count: int | None
    pages_without_text_layer: int | None
    check_max_chars: int | None
    quoted_credits: int | None
    error_code: DocumentErrorCode | str | None
    expires_at: str | None
    created_at: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class CorpusCoverage(Response):
    """Answer of ``GET /corpus/coverage``."""

    total_decisions: Count | None
    branches: list[dict[str, Any]]
    courts: list[dict[str, Any]]
    courts_returned: int | None
    courts_total: int | None
    corpus_floors: str | None
    coverage_ranges: dict[str, Any] | None
    as_of: str | None
    filter_coverage_caveats: str | None
    law_coverage: dict[str, Any] | None


@dataclass(slots=True, frozen=True, kw_only=True)
class CorpusFacets(Response):
    """Answer of ``GET /corpus/facets/{field}``. ``values`` maps a facet value to a count.

    ``norm`` is echoed back for ``field="cited_norms"``, else ``None``.
    """

    field: str
    applies_to: str | None
    values: dict[str, Count]
    total_values: int | None
    truncated: bool | None
    value_limit: int | None
    count_basis: str | None
    as_of: str | None
    norm: str | None
