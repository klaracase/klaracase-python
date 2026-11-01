"""Official Python client for the Klaracase REST API.

Klaracase covers German law only. It is a research tool. It gives no legal advice and does not
replace a lawyer's review. A ``not_found`` verdict means the citation was not found in the corpus;
it is not a claim that the citation is fabricated.
"""

from __future__ import annotations

from ._async import AsyncKlaracase
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
    ForbiddenError,
    InsufficientCreditsError,
    KlaracaseError,
    KlaracaseTimeoutError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    ValidationError,
)
from .types import (
    CitationCheck,
    CitationCheckDocument,
    CorpusCoverage,
    CorpusFacets,
    Credits,
    CrossTypeSearch,
    Datapackage,
    Decision,
    DecisionCitations,
    DecisionSearch,
    DeprecationNotice,
    Norm,
    ResponseMeta,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "ApiError",
    "AsyncKlaracase",
    "AuthenticationError",
    "CitationCheck",
    "CitationCheckDocument",
    "ConfigurationError",
    "ConflictError",
    "CorpusCoverage",
    "CorpusFacets",
    "Credits",
    "CrossTypeSearch",
    "Datapackage",
    "Decision",
    "DecisionCitations",
    "DecisionSearch",
    "DefaultAsyncHttpClient",
    "DefaultHttpClient",
    "DeprecationNotice",
    "DocumentFailedError",
    "DocumentTimeoutError",
    "ForbiddenError",
    "InsufficientCreditsError",
    "Klaracase",
    "KlaracaseError",
    "KlaracaseTimeoutError",
    "Norm",
    "NotFoundError",
    "RateLimitError",
    "ResponseMeta",
    "ServiceUnavailableError",
    "Timeout",
    "TransportError",
    "ValidationError",
    "__version__",
    "reset_deprecation_warnings",
]
