"""Official Python client for the Klaracase REST API.

Klaracase covers German law only. It is a research tool. It gives no legal advice and does not
replace a lawyer's review. A ``not_found`` verdict means the citation was not found in the corpus;
it is not a claim that the citation is fabricated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._core import reset_deprecation_warnings
from ._sync import Klaracase
from ._transport import (
    DEFAULT_TIMEOUT,
    DefaultAsyncHttpClient,
    DefaultHttpClient,
    Timeout,
)
from ._version import __version__
from .errors import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    DocumentFailedError,
    DocumentTimeoutError,
    ErrorCode,
    ForbiddenError,
    InsufficientCreditsError,
    KlaracaseError,
    KlaracaseTimeoutError,
    KnownErrorCode,
    NotFoundError,
    RateLimitError,
    ResponseShapeError,
    ServiceUnavailableError,
    TransportError,
    UnprocessableEntityError,
    ValidationError,
)
from .types import (
    AvailableRange,
    Branch,
    BranchCoverage,
    CheckScope,
    CitationCheck,
    CitationCheckDocument,
    CitationDepth,
    CitationDirection,
    CitationEdge,
    CitationSource,
    CitedStatute,
    Confidence,
    CorpusCoverage,
    CorpusFacets,
    CorpusRef,
    Count,
    CourtCount,
    CourtCoverage,
    CoverageRange,
    CoverageRanges,
    Credits,
    CrossTypeSearch,
    Datapackage,
    DatapackageDecision,
    Decision,
    DecisionCitationParams,
    DecisionCitations,
    DecisionMetadata,
    DecisionSearch,
    DecisionSearchParams,
    DeprecationNotice,
    DocumentErrorCode,
    DocumentStatus,
    DocumentType,
    EdgeAccounting,
    Evidence,
    Extraction,
    FacetField,
    FacetType,
    Finding,
    InstanceMix,
    Jurisdiction,
    LawCoverage,
    Lifecycle,
    MatchedDecision,
    Neighbours,
    Norm,
    NormBody,
    NormJurisdiction,
    NormLaw,
    NormLinks,
    NormVersion,
    Pagination,
    Progress,
    Qualifier,
    QueryExpansion,
    ReasonCount,
    Response,
    ResponseMeta,
    RunStatus,
    SearchHit,
    SearchJurisdiction,
    SearchMode,
    Sections,
    SectionTotal,
    SectionTotals,
    Snippet,
    ToolCall,
    UniqueCitation,
    Verdict,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "ApiError",
    "AsyncKlaracase",
    "AuthenticationError",
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
    "ConfigurationError",
    "ConflictError",
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
    "DecisionCitationParams",
    "DecisionCitations",
    "DecisionMetadata",
    "DecisionSearch",
    "DecisionSearchParams",
    "DefaultAsyncHttpClient",
    "DefaultHttpClient",
    "DeprecationNotice",
    "DocumentErrorCode",
    "DocumentFailedError",
    "DocumentStatus",
    "DocumentTimeoutError",
    "DocumentType",
    "EdgeAccounting",
    "ErrorCode",
    "Evidence",
    "Extraction",
    "FacetField",
    "FacetType",
    "Finding",
    "ForbiddenError",
    "InstanceMix",
    "InsufficientCreditsError",
    "Jurisdiction",
    "Klaracase",
    "KlaracaseError",
    "KlaracaseTimeoutError",
    "KnownErrorCode",
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
    "NotFoundError",
    "Pagination",
    "Progress",
    "Qualifier",
    "QueryExpansion",
    "RateLimitError",
    "ReasonCount",
    "Response",
    "ResponseMeta",
    "ResponseShapeError",
    "RunStatus",
    "SearchHit",
    "SearchJurisdiction",
    "SearchMode",
    "SectionTotal",
    "SectionTotals",
    "Sections",
    "ServiceUnavailableError",
    "Snippet",
    "Timeout",
    "ToolCall",
    "TransportError",
    "UniqueCitation",
    "UnprocessableEntityError",
    "ValidationError",
    "Verdict",
    "__version__",
    "reset_deprecation_warnings",
]


if TYPE_CHECKING:
    from ._async import AsyncKlaracase


def __getattr__(name: str) -> Any:
    """Import the async client on first use. It pulls in ``asyncio``, which a sync user skips."""
    if name == "AsyncKlaracase":
        from ._async import AsyncKlaracase  # noqa: PLC0415

        AsyncKlaracase.__module__ = __name__
        globals()[name] = AsyncKlaracase
        return AsyncKlaracase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _present_public_classes_as_top_level() -> None:
    """Show ``klaracase.Name`` in reprs, tracebacks and docs instead of the private module."""
    for name in __all__:
        obj = globals().get(name)
        if isinstance(obj, type):
            obj.__module__ = __name__


_present_public_classes_as_top_level()
