"""Errors raised by the Klaracase client.

``KlaracaseError`` is the base of every error that comes from the API or from the transport. It
carries the fields of the RFC 9457 problem the API sent: ``type``, ``title``, ``status``,
``detail`` and ``code``. Every other problem member is in ``extra``.

The 403 class is called ``ForbiddenError``, not ``PermissionError``, because Python already has a
builtin ``PermissionError`` (a filesystem error). The 422 class is called ``ValidationError``. The
timeout class is called ``KlaracaseTimeoutError`` because Python has a builtin ``TimeoutError``.

``ConfigurationError`` is not a ``KlaracaseError``. It reports a mistake in how you built the
client.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from .types import ApiBudget, CitationCheckDocument

__all__ = [
    "ApiError",
    "AuthenticationError",
    "ConfigurationError",
    "ConflictError",
    "DocumentFailedError",
    "DocumentTimeoutError",
    "ErrorCode",
    "ForbiddenError",
    "InsufficientCreditsError",
    "InsufficientCreditsReason",
    "KlaracaseError",
    "KlaracaseTimeoutError",
    "KnownErrorCode",
    "NotFoundError",
    "RateLimitError",
    "ResponseShapeError",
    "ServiceUnavailableError",
    "TokenLimitReachedError",
    "TransportError",
    "UnprocessableEntityError",
    "ValidationError",
    "error_class_for_status",
]


KnownErrorCode = Literal[
    # Middleware and framework
    "unauthenticated",
    "personal_access_token_required",
    "token_org_missing",
    "token_org_membership_lost",
    "pseudonymizer_token_refused",
    "two_factor_required",
    "token_ability_missing",
    "validation_failed",
    "rate_limited",
    "insufficient_credits",
    "token_limit_reached",
    "volume_cap",
    "backend_unavailable",
    "service_unavailable",
    "internal_error",
    "bad_request",
    "forbidden",
    "not_found",
    "method_not_allowed",
    "conflict",
    "payload_too_large",
    "unsupported_media_type",
    "client_error",
    # Operations
    "not_found_under_filter",
    "statute_superseded",
    "section_not_in_current_text",
    "document_unavailable",
    "search_timeout",
    "index_unavailable",
    "norm_family_unavailable",
    "ambiguous_aktenzeichen",
    "ids_unresolved",
    "page_undefined_at_this_depth",
    "text_too_long",
    "not_german_legal_text",
    "unrecognisable_norm_token",
    "invalid_reference",
    "range_not_supported",
    "historical_version_unavailable",
    "ambiguous",
    "sections_unavailable",
    "section_not_found",
    "rn_range_not_found",
    "official_headnote_not_located",
    "document_leitsatz_not_located",
    # Raised by this SDK
    "unknown",
    "client_validation",
    "wait_timeout",
    "response_shape",
]
"""The closed vocabulary of ``error.code`` that this SDK version knows."""

InsufficientCreditsReason = (
    Literal["api_budget_empty", "api_budget_not_available", "plan_credits_exhausted"] | str
)
"""``InsufficientCreditsError.reason``: a known value, or a plain string the API adds later."""

ErrorCode = KnownErrorCode | str
"""``error.code``: a known code, or a plain string for a code the API adds later."""


class ConfigurationError(Exception):
    """The client was built with a missing or invalid setting, for example no token.

    It is not part of the problem hierarchy: it has no ``code`` and no ``status``.
    """


class KlaracaseError(Exception):
    """Base class of every error that comes from the API or the transport.

    Attributes:
        type: The problem ``type`` URI. It is a name, not a page to fetch.
        title: The problem ``title``.
        status: The HTTP status, or ``None`` when the API did not answer.
        detail: The problem ``detail``. The API words it for a human.
        code: The machine-readable problem ``code``, for example ``insufficient_credits``.
        api_release: The ``X-Klaracase-Api-Release`` header of the answer, if there was one.
        extra: Every other member of the problem body, unchanged.
        body: The whole problem body as a dict, or ``None`` when the answer was not JSON.
        response_headers: The response headers, names in lower case. Empty without an answer.
        status_code: The same as ``status``.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        type: str | None = None,
        title: str | None = None,
        status: int | None = None,
        detail: str | None = None,
        code: ErrorCode | None = None,
        api_release: str | None = None,
        extra: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        response_headers: dict[str, str] | None = None,
    ) -> None:
        text = message or detail or title or code or type_name(self)
        super().__init__(text)
        self.message = text
        self.type = type
        self.title = title
        self.status = status
        self.detail = detail
        self.code = code
        self.api_release = api_release
        self.extra: dict[str, Any] = dict(extra) if extra else {}
        self.body = body
        self.response_headers: dict[str, str] = dict(response_headers) if response_headers else {}

    @property
    def status_code(self) -> int | None:
        """The HTTP status, an alias of ``status``."""
        return self.status

    @property
    def retryable(self) -> bool:
        """Whether sending the same request again later can succeed.

        True for a 429 (except the daily ``volume_cap``), a 503 and a transport error. A 402,
        including ``token_limit_reached``, is never retryable. The client already retried up to
        ``max_retries`` times before it raised.
        """
        if self.code in {"volume_cap", "token_limit_reached"}:
            return False
        return self.status in {429, 503} or isinstance(self, TransportError)

    def __repr__(self) -> str:
        parts = [f"status={self.status!r}", f"code={self.code!r}", f"detail={self.detail!r}"]
        return f"{type(self).__name__}({', '.join(parts)})"

    def __str__(self) -> str:
        prefix = f"[{self.status}] " if self.status is not None else ""
        suffix = f" ({self.code})" if self.code else ""
        return f"{prefix}{self.message}{suffix}"

    def __reduce__(self) -> tuple[Any, ...]:
        return (_rebuild, (type(self), dict(self.__dict__)))


def type_name(error: object) -> str:
    return type(error).__name__


def _rebuild(cls: type[KlaracaseError], state: dict[str, Any]) -> KlaracaseError:
    error = cls.__new__(cls)
    Exception.__init__(error, state.get("message"))
    error.__dict__.update(state)
    return error


class AuthenticationError(KlaracaseError):
    """HTTP 401: the token is missing, expired or revoked."""


class ForbiddenError(KlaracaseError):
    """HTTP 403: the token lacks an ability, or the organization refuses the call.

    ``required_ability`` is set when the problem is ``token_ability_missing``.
    """

    @property
    def required_ability(self) -> str | None:
        value = self.extra.get("required_ability")
        return value if isinstance(value, str) else None


class NotFoundError(KlaracaseError):
    """HTTP 404."""


class ConflictError(KlaracaseError):
    """HTTP 409."""


class ValidationError(KlaracaseError):
    """HTTP 422, or a request the client refused to send.

    A client-side refusal has ``code == "client_validation"`` and ``status is None``. ``errors``
    maps a field name to a list of messages when the API sent one.
    """

    @property
    def errors(self) -> dict[str, list[str]]:
        value = self.extra.get("errors")
        return cast("dict[str, list[str]]", value) if isinstance(value, dict) else {}


class InsufficientCreditsError(KlaracaseError):
    """HTTP 402: the call was refused for credits or for a limit. It is never retried.

    Nothing ran and nothing was charged. The code says which refusal it is. For
    ``insufficient_credits`` the organization has too few credits, and ``cost`` and ``balance``
    are set. For ``token_limit_reached`` the API key reached its own limit, and the error is the
    subclass :class:`TokenLimitReachedError`. That 402 has no ``cost`` and no ``balance``, so both
    read ``None``.

    For ``insufficient_credits``, ``reason`` says why the call could not be paid (API release
    0.96.0): ``api_budget_empty``, ``api_budget_not_available`` or a value this SDK does not know
    yet. Treat an unknown value like ``api_budget_not_available``. ``plan_credits_exhausted`` is
    reserved.

    ``top_up_url`` is a page for a human organization admin. This client never opens it. A program
    or an AI agent must not open it or follow it. Show it to your user.

    ``api_budget`` is the prepaid API budget as it stands, the same object as ``credits.api_budget``
    on an answer. The API serves it only while the API budget is available and the organization
    holds a budget or may load one.
    """

    @property
    def cost(self) -> int | None:
        return _int_member(self.extra, "cost")

    @property
    def balance(self) -> int | None:
        return _int_member(self.extra, "balance")

    @property
    def reason(self) -> InsufficientCreditsReason | None:
        """Why the call could not be paid, or ``None`` when the problem has no ``reason``."""
        return _str_member(self.extra, "reason")

    @property
    def top_up_url(self) -> str | None:
        """Where an organization admin loads the API budget. For a human. Never open it."""
        return _str_member(self.extra, "top_up_url")

    @property
    def api_budget(self) -> ApiBudget | None:
        """The API budget as it stands, or ``None`` when the problem has no such object."""
        value = self.extra.get("api_budget")
        if not isinstance(value, dict):
            return None
        from .types import ApiBudget  # noqa: PLC0415

        return ApiBudget.from_dict(cast("dict[str, Any]", value))


class TokenLimitReachedError(InsufficientCreditsError):
    """HTTP 402 ``token_limit_reached``: this API key used up its own credit limit.

    An organization admin set the limit for the key. Nothing ran and nothing was charged. Do not
    retry: the call fails until the limit resets at ``resets_at`` or an admin changes the limit.
    Stop, and report the refusal to your user.

    It is a subclass of :class:`InsufficientCreditsError`, because the HTTP status is 402. The
    body has no ``cost`` and no ``balance``, so both read ``None``.

    Attributes:
        unit: Always ``credits`` today.
        cap: The credit limit of this key for the period.
        spent: The credits this key used in the period, plan credits and API budget together.
        resets_at: When the credit period of the key ends and its count starts again, as an
            aware ``datetime``. ``None`` when the member is absent or not an ISO 8601 date-time.
        resets_at_raw: The same member as the string the API sent.
        settings_url: The page where an organization admin changes the limit. For a human. Never
            open it.
    """

    @property
    def unit(self) -> str | None:
        return _str_member(self.extra, "unit")

    @property
    def cap(self) -> int | None:
        return _int_member(self.extra, "cap")

    @property
    def spent(self) -> int | None:
        return _int_member(self.extra, "spent")

    @property
    def resets_at_raw(self) -> str | None:
        return _str_member(self.extra, "resets_at")

    @property
    def resets_at(self) -> datetime.datetime | None:
        raw = self.resets_at_raw
        if raw is None:
            return None
        try:
            return datetime.datetime.fromisoformat(raw)
        except ValueError:
            return None

    @property
    def settings_url(self) -> str | None:
        return _str_member(self.extra, "settings_url")


def _int_member(extra: dict[str, Any], key: str) -> int | None:
    value = extra.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_member(extra: dict[str, Any], key: str) -> str | None:
    value = extra.get(key)
    return value if isinstance(value, str) else None


class RateLimitError(KlaracaseError):
    """HTTP 429. ``retry_after_seconds`` is the wait the server asks for.

    The client retries short waits itself. This error means the wait was longer than 30 seconds
    (``volume_cap`` for example) or the retries ran out.
    """

    def __init__(self, *args: Any, retry_after_seconds: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class ServiceUnavailableError(KlaracaseError):
    """HTTP 503. Nothing ran and nothing was charged."""


class ApiError(KlaracaseError):
    """Any other HTTP error status, and any answer that is not a problem body."""


class TransportError(KlaracaseError):
    """No answer arrived: connection refused, DNS, TLS, a dropped connection or a timeout.

    The original ``httpx2`` exception is ``__cause__``.
    """


class KlaracaseTimeoutError(TransportError):
    """The answer took longer than the client ``timeout``."""


class DocumentFailedError(KlaracaseError):
    """``wait_until_ready`` saw the upload end with status ``failed``.

    ``code`` and ``error_code`` are the receipt's ``error_code``, for example ``encrypted_pdf``.
    ``document`` is the receipt.
    """

    def __init__(self, document: CitationCheckDocument) -> None:
        error_code = document.error_code
        detail = f"The document {document.id} failed with {error_code or 'an unknown error'}."
        super().__init__(detail=detail, code=error_code)
        self.document = document

    @property
    def error_code(self) -> str | None:
        return self.document.error_code


class DocumentTimeoutError(KlaracaseError):
    """``wait_until_ready`` ran out of time. ``document`` is the last receipt."""

    def __init__(self, document: CitationCheckDocument, timeout: float) -> None:
        detail = (
            f"The document {document.id} was not ready after {timeout:g} s "
            f"(last status: {document.status})."
        )
        super().__init__(detail=detail, code="wait_timeout")
        self.document = document
        self.timeout = timeout


class ResponseShapeError(KlaracaseError):
    """The answer is a JSON object that lacks an identity key (``id``, ``reference`` or ``field``).

    ``path`` names the missing key, for example ``findings[0].id``. This is not a mistake in your
    code: the API sent a body this SDK version cannot use. ``status`` is the HTTP status.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        status: int | None = None,
        api_release: str | None = None,
    ) -> None:
        super().__init__(
            message, code="response_shape", detail=message, status=status, api_release=api_release
        )
        self.path = path


UnprocessableEntityError = ValidationError
"""Another name for :class:`ValidationError` (HTTP 422), for readers who expect it."""

_BY_STATUS: dict[int, type[KlaracaseError]] = {
    401: AuthenticationError,
    402: InsufficientCreditsError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}


def error_class_for_status(status: int, code: str | None = None) -> type[KlaracaseError]:
    """Return the error class the HTTP status decides.

    A 402 with the code ``token_limit_reached`` is a :class:`TokenLimitReachedError`.
    """
    if status == 402 and code == "token_limit_reached":
        return TokenLimitReachedError
    return _BY_STATUS.get(status, ApiError)
