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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import CitationCheckDocument

__all__ = [
    "ApiError",
    "AuthenticationError",
    "ConfigurationError",
    "ConflictError",
    "DocumentFailedError",
    "DocumentTimeoutError",
    "ForbiddenError",
    "InsufficientCreditsError",
    "KlaracaseError",
    "KlaracaseTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TransportError",
    "ValidationError",
    "error_class_for_status",
]


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
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        type: str | None = None,
        title: str | None = None,
        status: int | None = None,
        detail: str | None = None,
        code: str | None = None,
        api_release: str | None = None,
        extra: dict[str, Any] | None = None,
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
        return value if isinstance(value, dict) else {}


class InsufficientCreditsError(KlaracaseError):
    """HTTP 402: the organization has too few credits. It is never retried."""

    @property
    def cost(self) -> int | None:
        value = self.extra.get("cost")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def balance(self) -> int | None:
        value = self.extra.get("balance")
        return value if isinstance(value, int) and not isinstance(value, bool) else None


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


def error_class_for_status(status: int) -> type[KlaracaseError]:
    """Return the error class the HTTP status decides."""
    return _BY_STATUS.get(status, ApiError)
