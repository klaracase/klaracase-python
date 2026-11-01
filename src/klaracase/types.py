"""Request value types and response types.

Request parameters are typed strictly with ``Literal`` unions. Response values that come from a
closed vocabulary are typed ``Literal[...] | str``: a value the server adds later stays a plain
string and never raises.

Every response is a frozen, slotted dataclass, nested at every level:

* one attribute per documented key, named like the wire key (``from`` is ``from_``);
* ``extra``: every key this SDK version does not model, at every depth (the API only adds keys);
* a wrong-typed value reads as ``None`` (``[]`` for a list, ``{}`` for a mapping) and never raises;
* an identity key (``id``, ``reference``, ``field``) is required. A body without it raises
  :class:`~klaracase.ResponseShapeError`.

A top-level response also has ``meta`` (the HTTP status, the API release, the headers and the
duration), ``raw`` (the parsed body, as received), ``credits`` (always a :class:`Credits`) and
``to_dict()`` (a deep copy of the body). Nothing is renamed, reordered, cleaned or translated.
"""

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as _field
from typing import Any, Literal, Self

from ._model import Model, decode_model

__all__ = [
    "AvailableRange",
    "Branch",
    "BranchCoverage",
    "CheckScope",
    "CitationCheck",
    "CitationCheckDocument",
    "CitationDepth",
    "CitationDirection",
    "CitationEdge",
    "CitationSource",
    "CitedStatute",
    "Confidence",
    "CorpusCoverage",
    "CorpusFacets",
    "CorpusRef",
    "Count",
    "CourtCount",
    "CourtCoverage",
    "CoverageRange",
    "CoverageRanges",
    "Credits",
    "CrossTypeSearch",
    "Datapackage",
    "DatapackageDecision",
    "Decision",
    "DecisionCitations",
    "DecisionMetadata",
    "DecisionSearch",
    "DeprecationNotice",
    "DocumentErrorCode",
    "DocumentStatus",
    "DocumentType",
    "EdgeAccounting",
    "Evidence",
    "Extraction",
    "FacetField",
    "FacetType",
    "Finding",
    "InstanceMix",
    "Jurisdiction",
    "LawCoverage",
    "Lifecycle",
    "MatchedDecision",
    "Neighbours",
    "Norm",
    "NormBody",
    "NormJurisdiction",
    "NormLaw",
    "NormLinks",
    "NormVersion",
    "Pagination",
    "Progress",
    "Qualifier",
    "QueryExpansion",
    "ReasonCount",
    "Response",
    "ResponseMeta",
    "RunStatus",
    "SearchHit",
    "SearchJurisdiction",
    "SearchMode",
    "SectionTotal",
    "SectionTotals",
    "Sections",
    "Snippet",
    "ToolCall",
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
Confidence = Literal["high", "medium", "low"]
"""Bands the relevance of a search row. ``None`` means not measured, never ``low``."""

Lifecycle = Literal["current", "repealed", "unconfirmed"]
Jurisdiction = Literal["DE", "EU", "XI"]

DOCUMENT_TERMINAL_STATUSES = frozenset({"ready", "failed"})


@dataclass(frozen=True, slots=True, kw_only=True)
class ResponseMeta:
    """What the transport knows about an answer.

    Attributes:
        status: The HTTP status (200 or 202). It is 0 on an object built with ``from_dict``.
        api_release: The ``X-Klaracase-Api-Release`` header, or ``None`` if it was absent.
        request_duration: Seconds spent on the HTTP exchange that produced this answer.
        headers: The response headers, names in lower case.
    """

    status: int = 0
    api_release: str | None = None
    request_duration: float = 0.0
    headers: dict[str, str] = _field(default_factory=dict[str, str], repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeprecationNotice:
    """The raw ``Deprecation``, ``Sunset`` and ``Link`` header values of an answer."""

    deprecation: str | None
    sunset: str | None
    link: str | None
    method: str
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Count(Model):
    """A count that can be a lower bound: ``is_floor`` is true when ``value`` is a floor."""

    value: int | None = None
    is_floor: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Credits(Model):
    """The ``credits`` object of an answer.

    A superadmin answer has ``metered=False`` and ``None`` for the other two. A body without
    ``credits`` gives an empty ``Credits``, so ``response.credits.cost`` always type-checks.
    """

    metered: bool | None = None
    cost: int | None = None
    credits_remaining: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Response(Model):
    """Base of every top-level response.

    Attributes:
        meta: HTTP status, API release, headers and request duration.
        raw: The parsed JSON body, as received.
        api_version: The API version the body was served under.
        changelog_url: Where the API changes are listed.
        credits: What the call cost. Always set.
    """

    meta: ResponseMeta = _field(default_factory=ResponseMeta, metadata={"wire": False})
    raw: dict[str, Any] = _field(
        default_factory=dict, repr=False, compare=False, metadata={"wire": False}
    )
    api_version: str | None = None
    changelog_url: str | None = None
    credits: Credits = _field(default_factory=Credits)

    @classmethod
    def from_body(cls, body: Mapping[str, Any], meta: ResponseMeta) -> Self:
        """Build the response from a parsed body and the transport facts."""
        return decode_model(cls, body, "", {"meta": meta, "raw": dict(body)})

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> Self:
        """Build the response from a parsed JSON object. ``meta`` is then empty."""
        return cls.from_body(body, ResponseMeta())

    def to_dict(self) -> dict[str, Any]:
        """Return the parsed body unchanged (a deep copy, without ``meta``)."""
        return copy.deepcopy(self.raw)


@dataclass(frozen=True, slots=True, kw_only=True)
class Snippet(Model):
    text: str | None = None
    rn: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchHit(Model):
    """One row of a search: a decision row, or in ``search`` a law row.

    A decision row has ``aktenzeichen``, ``court``, ``date`` and ``document_type``. A law row
    has ``abbreviation``, ``law_type`` and ``jurisdiction``. ``id`` feeds ``decisions.get``.
    """

    id: str
    artifact_type: str | None = None
    aktenzeichen: str | None = None
    court: str | None = None
    date: str | None = None
    document_type: DocumentType | str | None = None
    title: str | None = None
    snippet: str | None = None
    snippets: list[Snippet] = _field(default_factory=list[Snippet])
    chunk_title: str | None = None
    rn_range: str | None = None
    fundstelle: str | None = None
    breadcrumb: str | None = None
    abbreviation: str | None = None
    law_type: str | None = None
    jurisdiction: Jurisdiction | str | None = None
    fortgeltung_checked: bool | None = None
    fortgeltung_note: str | None = None
    confidence: Confidence | str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryExpansion(Model):
    status: str | None = None
    applied: bool | None = None
    reason: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusRef(Model):
    """The corpus decision that a citation edge points to."""

    artifact_id: str | None = None
    court: str | None = None
    date: str | None = None
    az: str | None = None
    document_type: DocumentType | str | None = None
    ecli: str | None = None
    corpus_url: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationEdge(Model):
    """One citation. ``hop`` is set in the citation graph and absent in a data package."""

    reference_canonical: str | None = None
    reference_role: str | None = None
    resolution_status: str | None = None
    in_corpus: bool | None = None
    corpus: CorpusRef | None = None
    from_artifact_id: str | None = None
    hop: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSearch(Response):
    """Answer of ``GET /decisions/search``."""

    results: list[SearchHit] = _field(default_factory=list[SearchHit])
    payload_truncated: bool | None = None
    total_available: Count | None = None
    total_available_basis: str | None = None
    candidate_pool: int | None = None
    pool_exhaustive: bool | None = None
    truncated: bool | None = None
    page: int | None = None
    limit: int | None = None
    mode: SearchMode | str | None = None
    frequently_cited_by_results: list[Any] = _field(default_factory=list[Any])
    query_expansion: QueryExpansion | None = None
    top_confidence: Confidence | str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Sections(Model):
    laws: list[SearchHit] = _field(default_factory=list[SearchHit])
    decisions: list[SearchHit] = _field(default_factory=list[SearchHit])


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionTotal(Model):
    total_available: Count | None = None
    total_available_basis: str | None = None
    candidate_pool: int | None = None
    pool_exhaustive: bool | None = None
    truncated: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionTotals(Model):
    laws: SectionTotal | None = None
    decisions: SectionTotal | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CrossTypeSearch(Response):
    """Answer of ``GET /search``: ``sections`` holds ``laws`` and ``decisions``."""

    sections: Sections | None = None
    section_totals: SectionTotals | None = None
    limit: int | None = None
    total_available: Count | None = None
    total_available_basis: str | None = None
    pool_exhaustive: bool | None = None
    truncated: bool | None = None
    mode: SearchMode | str | None = None
    query_expansion: QueryExpansion | None = None
    frequently_cited_by_results: list[Any] = _field(default_factory=list[Any])
    norms_cited_by_decision_results: list[Any] = _field(default_factory=list[Any])
    top_confidence: Confidence | str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionMetadata(Model):
    document_type: DocumentType | str | None = None
    ecli: str | None = None
    file_numbers: list[str] = _field(default_factory=list[str])


@dataclass(frozen=True, slots=True, kw_only=True)
class AvailableRange(Model):
    """A span of Randnummern (``rn``): what exists, or in ``returned_range`` what was served."""

    rn_from: int | None = None
    rn_to: int | None = None
    rn_source: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Decision(Response):
    """Answer of ``GET /decisions/{id}``."""

    id: str
    aktenzeichen: str | None = None
    court: str | None = None
    date: str | None = None
    jurisdiction: Jurisdiction | str | None = None
    metadata: DecisionMetadata | None = None
    fortgeltung_checked: bool | None = None
    fortgeltung_note: str | None = None
    full_text: str | None = _field(default=None, repr=False)
    text_length: int | None = None
    truncated: bool | None = None
    rn_source: str | None = None
    rn_source_note: str | None = None
    available_sections: list[str] = _field(default_factory=list[str])
    available_range: AvailableRange | None = None
    returned_range: AvailableRange | None = None
    available_range_scope: str | None = None
    has_rn_anchors: bool | None = None

    @property
    def ecli(self) -> str | None:
        """The ECLI, read from ``metadata``."""
        return self.metadata.ecli if self.metadata is not None else None

    @property
    def document_type(self) -> DocumentType | str | None:
        """The document type (Urteil, Beschluss, ...), read from ``metadata``."""
        return self.metadata.document_type if self.metadata is not None else None


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationSource(Model):
    id: str | None = None
    aktenzeichen: str | None = None
    court: str | None = None
    date: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Pagination(Model):
    page: int | None = None
    page_size: int | None = None
    max_page: int | None = None
    reachable_distinct_max: int | None = None
    references_pages: int | None = None
    referenced_by_pages: int | None = None
    has_more_references: bool | None = None
    has_more_referenced_by: bool | None = None
    applies_at_depth: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCitations(Response):
    """Answer of ``GET /decisions/{id}/citations``."""

    source: CitationSource | None = None
    references: list[CitationEdge] = _field(default_factory=list[CitationEdge])
    referenced_by: list[CitationEdge] = _field(default_factory=list[CitationEdge])
    served_direction: str | None = None
    served_references_total: int | None = None
    served_referenced_by_total: int | None = None
    references_total: int | None = None
    references_resolved_total: int | None = None
    referenced_by_total: int | None = None
    references_unresolved_total: int | None = None
    references_withheld_reasons: list[Any] = _field(default_factory=list[Any])
    totals_scope: str | None = None
    per_direction_cap: int | None = None
    unresolved_cap: int | None = None
    node_cap: int | None = None
    truncated: bool | None = None
    nodes_omitted: int | None = None
    payload_truncated: bool | None = None
    pagination: Pagination | None = None
    fortgeltung_checked: bool | None = None
    fortgeltung_note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NormLaw(Model):
    id: str | None = None
    abbreviation: str | None = None
    source_abbreviation: str | None = None
    official_name: str | None = None
    law_level: str | None = None
    jurisdiction: Jurisdiction | str | None = None
    source_url: str | None = None
    upstream_status: str | None = None
    upstream_last_seen_at: str | None = None
    upstream_missing_since: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NormBody(Model):
    """The norm itself. ``text`` is ``None`` for a repealed stub."""

    number: str | None = None
    title: str | None = None
    lifecycle: Lifecycle | str | None = None
    text: str | None = _field(default=None, repr=False)
    absatz_identifiers: list[str] = _field(default_factory=list[str])
    chars: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Qualifier(Model):
    """A part of the reference you asked for (an Absatz, for example) and whether it exists."""

    type: str | None = None
    value: str | None = None
    checked: bool | None = None
    present: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NormVersion(Model):
    id: str | None = None
    last_amendment_date: str | None = None
    last_amendment_date_basis: str | None = None
    source_fetched_at: str | None = None
    source_last_seen_at: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Neighbours(Model):
    previous: str | None = None
    next: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall(Model):
    """A ready call: the MCP tool name and its arguments."""

    tool: str | None = None
    arguments: dict[str, Any] = _field(default_factory=dict[str, Any])


@dataclass(frozen=True, slots=True, kw_only=True)
class NormLinks(Model):
    decisions_citing: ToolCall | None = None
    decisions_citing_url: str | None = None
    self_url: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Norm(Response):
    """Answer of ``GET /norms/{reference}``."""

    reference: str
    requested_reference: str | None = None
    law: NormLaw | None = None
    norm: NormBody | None = None
    requested_qualifiers: list[Qualifier] = _field(default_factory=list[Qualifier])
    version: NormVersion | None = None
    neighbours: Neighbours | None = None
    links: NormLinks | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DatapackageDecision(Model):
    id: str
    aktenzeichen: str | None = None
    court: str | None = None
    date: str | None = None
    document_type: DocumentType | str | None = None
    ecli: str | None = None
    jurisdiction: Jurisdiction | str | None = None
    excerpt: str | None = _field(default=None, repr=False)
    excerpt_span: str | None = None
    text_length: int | None = None
    truncated: bool | None = None
    fortgeltung_checked: bool | None = None
    fortgeltung_note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EdgeAccounting(Model):
    from_artifact_id: str | None = None
    unit: str | None = None
    edges_total: int | None = None
    edges_included: int | None = None
    edges_resolved_included: int | None = None
    edges_unresolved_included: int | None = None
    edges_resolved_total: int | None = None
    edges_unresolved_total: int | None = None
    targets_resolved_included: int | None = None
    targets_resolved_total: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Datapackage(Response):
    """Answer of ``POST /datapackages``."""

    decisions: list[DatapackageDecision] = _field(default_factory=list[DatapackageDecision])
    citation_edges: list[CitationEdge] = _field(default_factory=list[CitationEdge])
    edge_accounting: list[EdgeAccounting] = _field(default_factory=list[EdgeAccounting])
    per_source_resolved_target_cap: int | None = None
    per_source_unresolved_edge_row_cap: int | None = None
    requested: int | None = None
    included: int | None = None
    deduped: int | None = None
    text_mode: str | None = None
    max_chars: int | None = None
    truncated: bool | None = None
    payload_truncated: bool | None = None
    assembled_at: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Progress(Model):
    citations_total: int | None = None
    citations_checked: int | None = None
    unique_citations_total: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReasonCount(Model):
    category: str | None = None
    count: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UniqueCitation(Model):
    """One distinct citation of a run, with every spelling and how often it occurs."""

    key_basis: str | None = None
    target_artifact_id: str | None = None
    canonical: str | None = None
    spellings: list[str] = _field(default_factory=list[str])
    occurrences: int | None = None
    verdict: Verdict | str | None = None
    reference_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Extraction(Model):
    """What the extractor found, and what it dropped or could not verify."""

    detected: int | None = None
    dropped: int | None = None
    dropped_unreadable: int | None = None
    dropped_truncation: int | None = None
    dropped_trailing_noun: int | None = None
    dropped_stacked_subdivision: int | None = None
    dropped_refused_collision: int | None = None
    dropped_by_token: list[Any] = _field(default_factory=list[Any])
    dropped_unreadable_texts: list[Any] = _field(default_factory=list[Any])
    refused_contract_collision: list[Any] = _field(default_factory=list[Any])
    not_verifiable: int | None = None
    not_verifiable_by_type: list[Any] = _field(default_factory=list[Any])
    possible_citations_unparsed: int | None = None
    possible_citations_unparsed_texts: list[Any] = _field(default_factory=list[Any])


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchedDecision(Model):
    artifact_id: str | None = None
    ecli: str | None = None
    court: str | None = None
    date: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckScope(Model):
    subdivision: str | None = None
    article_text_available: bool | None = None
    article_text_read: bool | None = None
    court: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence(Model):
    """Why a finding got its verdict. ``citation_date_source`` is ``sentence``,
    ``reference_date`` or ``none``."""

    reason: str | None = None
    match_strength: str | None = None
    citation_date_source: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding(Model):
    """One citation found in the checked text.

    ``start_offset`` and ``end_offset`` are Unicode code point offsets into the exact string
    you sent. Python strings index by code point, so ``excerpt`` slices them directly.
    """

    id: str
    raw_text: str | None = None
    canonical: str | None = None
    type: str | None = None
    role: str | None = None
    verdict: Verdict | str | None = None
    external_status: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    occurrence_index: int | None = None
    confidence: Confidence | str | None = None
    matched_decision: MatchedDecision | None = None
    subdivision_check: str | None = None
    subdivision_advisory: str | None = None
    check_scope: CheckScope | None = None
    ambiguity_advisory: str | None = None
    coverage: Any = None
    coverage_boundary: Any = None
    coverage_advisory: str | None = None
    evidence: Evidence | None = None
    disputed_at: str | None = None

    def excerpt(self, text: str) -> str | None:
        """Return the part of ``text`` this finding points at, or ``None`` without offsets.

        ``text`` must be the exact string you sent to the check.
        """
        if self.start_offset is None or self.end_offset is None:
            return None
        return text[self.start_offset : self.end_offset]


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationCheck(Response):
    """A citation check run (``POST /citation-checks`` and ``GET /citation-checks/{run}``).

    ``verdict_counts`` maps a verdict name to a count. ``findings`` carries one entry per
    citation found, with offsets into the text you sent.
    """

    id: str
    status: RunStatus | str | None = None
    source: str | None = None
    progress: Progress | None = None
    verdict_counts: dict[str, int] = _field(default_factory=dict[str, int])
    partial: bool | None = None
    unverified_count: int | None = None
    reason_counts: list[ReasonCount] = _field(default_factory=list[ReasonCount])
    unique_citations: list[UniqueCitation] = _field(default_factory=list[UniqueCitation])
    extraction: Extraction | None = None
    notes: list[Any] = _field(default_factory=list[Any])
    findings_unavailable_reason: str | None = None
    findings_purged_at: str | None = None
    findings: list[Finding] = _field(default_factory=list[Finding])
    submitted_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    payload_truncated: bool | None = None

    def by_verdict(self) -> dict[str, list[Finding]]:
        """Group the findings by verdict, in the order the API sent them.

        A finding without a verdict is filed under ``"unknown"``.
        """
        groups: dict[str, list[Finding]] = {}
        for finding in self.findings:
            groups.setdefault(finding.verdict or "unknown", []).append(finding)
        return groups


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationCheckDocument(Response):
    """The receipt of an upload. It never holds the text."""

    id: str
    filename: str | None = None
    format: str | None = None
    status: DocumentStatus | str | None = None
    char_count: int | None = None
    page_count: int | None = None
    pages_without_text_layer: int | None = None
    check_max_chars: int | None = None
    quoted_credits: int | None = None
    error_code: DocumentErrorCode | str | None = None
    expires_at: str | None = None
    created_at: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InstanceMix(Model):
    federal: Count | None = None
    appellate: Count | None = None
    first_instance_and_regional: Count | None = None
    other: Count | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CourtCount(Model):
    court: str | None = None
    count: Count | None = None
    earliest: str | None = None
    latest: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CourtCoverage(Model):
    court: str | None = None
    branch: Branch | str | None = None
    count: Count | None = None
    earliest: str | None = None
    latest: str | None = None
    court_founding_year: int | None = None
    court_founding_basis: str | None = None
    has_dates_below_floor: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BranchCoverage(Model):
    branch: Branch | str | None = None
    count: Count | None = None
    earliest: str | None = None
    latest: str | None = None
    court_founding_year: int | None = None
    court_founding_basis: str | None = None
    has_dates_below_floor: bool | None = None
    instance_mix: InstanceMix | None = None
    top_courts: list[CourtCount] = _field(default_factory=list[CourtCount])


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageRange(Model):
    """A date range a court is covered for. The wire key ``from`` is ``from_`` here."""

    bucket: str | None = None
    court: str | None = None
    label: str | None = None
    from_: str | None = None
    until: str | None = None
    sources: list[str] = _field(default_factory=list[str])
    exhaustive: bool | None = None
    ocr: bool | None = None
    note: str | None = None
    holdings_earliest: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageRanges(Model):
    note: str | None = None
    scope: str | None = None
    verified_at: str | None = None
    ranges: list[CoverageRange] = _field(default_factory=list[CoverageRange])


@dataclass(frozen=True, slots=True, kw_only=True)
class LawCoverage(Model):
    note: str | None = None
    eu: list[str] = _field(default_factory=list[str])
    international: list[str] = _field(default_factory=list[str])


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusCoverage(Response):
    """Answer of ``GET /corpus/coverage``."""

    total_decisions: Count | None = None
    branches: list[BranchCoverage] = _field(default_factory=list[BranchCoverage])
    courts: list[CourtCoverage] = _field(default_factory=list[CourtCoverage])
    courts_returned: int | None = None
    courts_total: int | None = None
    corpus_floors: str | None = None
    coverage_ranges: CoverageRanges | None = None
    as_of: str | None = None
    filter_coverage_caveats: str | None = None
    law_coverage: LawCoverage | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusFacets(Response):
    """Answer of ``GET /corpus/facets/{field}``. ``values`` maps a facet value to a count.

    ``norm`` is echoed back for ``field="cited_norms"``, else ``None``.
    """

    field: str
    applies_to: str | None = None
    values: dict[str, Count] = _field(default_factory=dict[str, Count])
    total_values: int | None = None
    truncated: bool | None = None
    value_limit: int | None = None
    count_basis: str | None = None
    as_of: str | None = None
    norm: str | None = None
