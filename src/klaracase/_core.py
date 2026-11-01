"""The transport core shared by the sync and the async client.

Everything that is not input or output lives here: configuration, request building, the retry
policy and problem parsing. ``Klaracase`` and ``AsyncKlaracase`` only move bytes and sleep.
"""

from __future__ import annotations

import logging
import os
import platform
import random
import threading
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Generic, TypeVar, cast
from urllib.parse import quote, urlsplit

from . import _transport as transport
from ._logging import LOGGER, setup_env_logging
from ._version import __version__
from .errors import (
    ApiError,
    ConfigurationError,
    KlaracaseError,
    KlaracaseTimeoutError,
    RateLimitError,
    ResponseShapeError,
    TransportError,
    ValidationError,
    error_class_for_status,
)
from .types import DeprecationNotice, Response, ResponseMeta

DEFAULT_BASE_URL = "https://klaracase.de/api/v1"
TOKEN_ENV_VAR = "KLARACASE_API_TOKEN"
DEFAULT_TIMEOUT = transport.DEFAULT_TIMEOUT
DEFAULT_MAX_RETRIES = 2

BACKOFF_BASE_SECONDS = 0.5
BACKOFF_CAP_SECONDS = 8.0
MAX_SLEEP_SECONDS = 30.0
DETAIL_LIMIT = 1000
RETRY_STATUSES = frozenset({429, 503})
NEVER_RETRY_CODES = frozenset({"volume_cap", "token_limit_reached"})
"""Codes the client raises at once, whatever the status. A wait does not help for these."""
UNKNOWN_CODE = "unknown"

T = TypeVar("T", bound=Response)

DeprecationHook = Callable[[DeprecationNotice], None]


@dataclass(slots=True, frozen=True)
class RequestOptions:
    """Per-call overrides: a timeout, extra headers and extra query parameters."""

    timeout: float | transport.Timeout | None = None
    extra_headers: Mapping[str, str] | None = None
    extra_query: Mapping[str, str | int | bool] | None = None


def request_options(
    timeout: float | transport.Timeout | None,
    extra_headers: Mapping[str, str] | None,
    extra_query: Mapping[str, str | int | bool] | None,
) -> RequestOptions | None:
    """Validate the per-call options. Return ``None`` when the caller set none."""
    if timeout is None and not extra_headers and not extra_query:
        return None
    if timeout is not None:
        check_timeout(timeout)
    return RequestOptions(timeout, extra_headers, extra_query)


@dataclass(slots=True, frozen=True)
class Operation(Generic[T]):
    """One API call, fully described and already validated.

    ``path`` is the path below the base URL with every path parameter already percent-encoded.
    ``query`` is a list of name/value pairs in wire form.
    """

    method: str
    path: str
    response_cls: type[T]
    query: Sequence[tuple[str, str]] = ()
    json_body: Mapping[str, Any] | None = None
    files: Mapping[str, tuple[str, bytes, str]] | None = None
    options: RequestOptions | None = None


def replace_options(operation: Operation[T], options: RequestOptions) -> Operation[T]:
    """Return ``operation`` with per-call options attached."""
    return replace(operation, options=options)


def quote_segment(value: str) -> str:
    """Encode a path parameter as ONE segment.

    Every byte outside ``A-Za-z0-9-._~`` becomes ``%XX`` with upper-case hex. A slash becomes
    ``%2F``, a space ``%20``, ``§`` becomes ``%C2%A7``.
    """
    return quote(value, safe="")


def query_pairs(params: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Turn keyword arguments into wire query pairs.

    ``None`` and empty sequences are not sent. Booleans become ``true`` or ``false``. A sequence is
    sent as ``name[]`` repeated, in order. ``False`` and ``0`` are values and are sent.
    """
    pairs: list[tuple[str, str]] = []
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            pairs.extend((f"{name}[]", _scalar(item)) for item in cast("Sequence[Any]", value))
            continue
        pairs.append((name, _scalar(value)))
    return pairs


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def check_timeout(timeout: object) -> None:
    """Raise ``ConfigurationError`` unless ``timeout`` is seconds above 0 or a ``Timeout``."""
    if isinstance(timeout, transport.Timeout):
        return
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ConfigurationError("timeout must be a number of seconds above 0 or a Timeout.")


def check_max_retries(max_retries: object) -> None:
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise ConfigurationError("max_retries must be an integer of 0 or more.")


def client_validation_error(message: str) -> ValidationError:
    return ValidationError(detail=message, code="client_validation", title="Invalid request")


_deprecation_lock = threading.Lock()
_deprecation_warned = False


def reset_deprecation_warnings() -> None:
    """Forget that a deprecation was already surfaced in this process. Meant for tests."""
    global _deprecation_warned  # noqa: PLW0603
    with _deprecation_lock:
        _deprecation_warned = False


def _claim_deprecation_slot() -> bool:
    global _deprecation_warned  # noqa: PLW0603
    with _deprecation_lock:
        if _deprecation_warned:
            return False
        _deprecation_warned = True
        return True


def default_deprecation_hook(notice: DeprecationNotice) -> None:
    """Warn with ``DeprecationWarning``. Python's own warning filter decides what is shown."""
    parts = [f"The Klaracase API deprecated {notice.method} {notice.url}."]
    if notice.sunset:
        parts.append(f"Sunset: {notice.sunset}.")
    if notice.link:
        parts.append(f"Link: {notice.link}")
    warnings.warn(" ".join(parts), DeprecationWarning, stacklevel=2)


@dataclass(slots=True, frozen=True)
class Retry:
    """The core asks the caller to sleep ``wait`` seconds and send the request again."""

    wait: float


@dataclass(slots=True)
class Core:
    """Configuration plus the pure parts of a request cycle."""

    token: str = field(repr=False)
    base_url: str
    timeout: float | transport.Timeout
    max_retries: int
    user_agent: str
    on_deprecation: DeprecationHook
    monotonic: Callable[[], float]
    uniform: Callable[[float, float], float] = field(default=random.uniform)
    extra_headers: Mapping[str, str] = field(default_factory=dict[str, str])

    def with_options(
        self,
        *,
        timeout: float | transport.Timeout | None,
        max_retries: int | None,
        extra_headers: Mapping[str, str] | None,
    ) -> Core:
        """Return a copy with some settings replaced. ``None`` keeps the current value."""
        changes: dict[str, Any] = {}
        if timeout is not None:
            check_timeout(timeout)
            changes["timeout"] = (
                timeout if isinstance(timeout, transport.Timeout) else float(timeout)
            )
        if max_retries is not None:
            check_max_retries(max_retries)
            changes["max_retries"] = max_retries
        if extra_headers:
            changes["extra_headers"] = {**self.extra_headers, **extra_headers}
        return replace(self, **changes)

    @classmethod
    def create(
        cls,
        *,
        token: str | None,
        base_url: str,
        timeout: float | transport.Timeout,
        max_retries: int,
        user_agent_suffix: str | None,
        on_deprecation: DeprecationHook | None,
        monotonic: Callable[[], float] | None,
    ) -> Core:
        setup_env_logging()
        resolved = token if token is not None else os.environ.get(TOKEN_ENV_VAR)
        if resolved is None or not resolved.strip():
            raise ConfigurationError(
                f"No API token. Pass token=... or set the {TOKEN_ENV_VAR} environment variable. "
                "Create a token at https://klaracase.de/settings/api-tokens."
            )
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ConfigurationError(
                f"Invalid base_url {base_url!r}: it needs an http or https scheme and a host."
            )
        check_max_retries(max_retries)
        check_timeout(timeout)
        user_agent = f"klaracase-python/{__version__} python/{platform.python_version()}"
        if user_agent_suffix:
            user_agent = f"{user_agent} {user_agent_suffix}"
        return cls(
            token=resolved.strip(),
            base_url=base_url.rstrip("/"),
            timeout=timeout if isinstance(timeout, transport.Timeout) else float(timeout),
            max_retries=max_retries,
            user_agent=user_agent,
            on_deprecation=on_deprecation or default_deprecation_hook,
            monotonic=monotonic or time.monotonic,
        )

    def request_kwargs(self, operation: Operation[Any]) -> dict[str, Any]:
        """Arguments for the ``build_request`` method of the HTTP client."""
        options = operation.options
        headers = _merge_headers(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
            self.extra_headers,
            options.extra_headers if options else None,
        )
        timeout = options.timeout if options and options.timeout is not None else self.timeout
        kwargs: dict[str, Any] = {
            "method": operation.method,
            "url": self.base_url + operation.path,
            "headers": headers,
            "timeout": timeout,
        }
        query = _merge_query(operation.query, options.extra_query if options else None)
        if query:
            kwargs["params"] = query
        if operation.json_body is not None:
            kwargs["json"] = operation.json_body
        if operation.files is not None:
            kwargs["files"] = dict(operation.files)
        return kwargs

    def backoff(self, retries_so_far: int) -> float:
        """Exponential backoff with full jitter: 0.5 s, 1 s, 2 s, ... capped at 8 s."""
        ceiling = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2**retries_so_far))
        return self.uniform(0.0, ceiling)

    def transport_wait(
        self, operation: Operation[Any], retries_so_far: int, exc: BaseException
    ) -> float | None:
        """Seconds to wait before retrying after a transport error, or ``None`` to give up.

        Only GET is retried: a POST whose connection dropped may have run.
        """
        attempt = retries_so_far + 1
        if operation.method != "GET" or retries_so_far >= self.max_retries:
            LOGGER.info(
                "%s %s -> %s, attempt %d, giving up",
                operation.method,
                operation.path,
                type(exc).__name__,
                attempt,
            )
            return None
        wait = self.backoff(retries_so_far)
        LOGGER.info(
            "%s %s -> %s, attempt %d, retry in %.2f s",
            operation.method,
            operation.path,
            type(exc).__name__,
            attempt,
            wait,
        )
        return wait

    def log_attempt(self, operation: Operation[Any], retries_so_far: int) -> None:
        """Log the start of an attempt at DEBUG: the query parameter names, never the values."""
        if LOGGER.isEnabledFor(logging.DEBUG):
            names = sorted({name for name, _ in operation.query})
            LOGGER.debug(
                "%s %s attempt %d query=%s",
                operation.method,
                operation.path,
                retries_so_far + 1,
                names,
            )

    def transport_error(self, exc: transport.RequestError) -> TransportError:
        cls = (
            KlaracaseTimeoutError if isinstance(exc, transport.TimeoutException) else TransportError
        )
        text = str(exc) or type(exc).__name__
        return cls(f"No answer from the Klaracase API: {text}", detail=text)

    def evaluate(
        self,
        operation: Operation[T],
        response: transport.HttpResponse,
        retries_so_far: int,
        started: float,
    ) -> T | Retry:
        """Turn an answer into a response object, a retry request, or a raised error."""
        duration = max(0.0, self.monotonic() - started)
        attempt = retries_so_far + 1
        self._surface_deprecation(operation, response)
        if response.is_success:
            LOGGER.info(
                "%s %s -> %d, attempt %d, %.3f s",
                operation.method,
                operation.path,
                response.status_code,
                attempt,
                duration,
            )
            return self._parse_success(operation, response, duration)
        error = self.error_from_response(response)
        wait = self._retry_wait(response, error, retries_so_far)
        if wait is None:
            LOGGER.info(
                "%s %s -> %d (%s), attempt %d, giving up",
                operation.method,
                operation.path,
                response.status_code,
                error.code,
                attempt,
            )
            raise error
        LOGGER.info(
            "%s %s -> %d (%s), attempt %d, retry in %.2f s",
            operation.method,
            operation.path,
            response.status_code,
            error.code,
            attempt,
            wait,
        )
        return Retry(wait)

    def _parse_success(
        self, operation: Operation[T], response: transport.HttpResponse, duration: float
    ) -> T:
        release = response.headers.get("x-klaracase-api-release")
        body = json_object(response)
        if body is None:
            raise ApiError(
                "The API answered with a body that is not a JSON object.",
                status=response.status_code,
                code=UNKNOWN_CODE,
                detail=response.text[:DETAIL_LIMIT],
                api_release=release,
            )
        meta = ResponseMeta(
            status=response.status_code,
            api_release=release,
            request_duration=duration,
            headers=lower_headers(response),
        )
        try:
            return operation.response_cls.from_body(body, meta)
        except ResponseShapeError as error:
            error.status = response.status_code
            error.api_release = release
            raise

    def error_from_response(self, response: transport.HttpResponse) -> KlaracaseError:
        """Build the error class that the HTTP status decides."""
        status = response.status_code
        release = response.headers.get("x-klaracase-api-release")
        text = response.text
        body = json_object(response)
        code = body.get("code") if body is not None else None
        cls = error_class_for_status(status, code if isinstance(code, str) else None)
        header_wait = _header_seconds(response.headers.get("retry-after"))
        if body is not None and isinstance(body.get("code"), str):
            standard = {"type", "title", "detail", "status", "code"}
            kwargs: dict[str, Any] = {
                "type": _optional_str(body.get("type")),
                "title": _optional_str(body.get("title")),
                "detail": _optional_str(body.get("detail")),
                "code": body["code"],
                "status": status,
                "api_release": release,
                "extra": {k: v for k, v in body.items() if k not in standard},
                "body": body,
                "response_headers": lower_headers(response),
            }
            if cls is RateLimitError:
                kwargs["retry_after_seconds"] = _number(
                    body.get("retry_after_seconds"), header_wait
                )
            return cls(**kwargs)
        kwargs = {
            "title": response.reason_phrase or None,
            "detail": text[:DETAIL_LIMIT],
            "code": UNKNOWN_CODE,
            "status": status,
            "api_release": release,
            "body": body,
            "response_headers": lower_headers(response),
        }
        if cls is RateLimitError:
            kwargs["retry_after_seconds"] = header_wait
        message = f"HTTP {status} without a problem body."
        return cls(message, **kwargs)

    def _retry_wait(
        self, response: transport.HttpResponse, error: KlaracaseError, retries_so_far: int
    ) -> float | None:
        """Seconds to sleep before the next attempt, or ``None`` to raise the error now."""
        if response.status_code not in RETRY_STATUSES or retries_so_far >= self.max_retries:
            return None
        if error.code in NEVER_RETRY_CODES:
            return None
        stated = _number(error.extra.get("retry_after_seconds"), None)
        if stated is None:
            stated = _header_seconds(response.headers.get("retry-after"))
        if stated is None:
            return self.backoff(retries_so_far)
        if stated > MAX_SLEEP_SECONDS:
            return None
        return max(0.0, stated)

    def _surface_deprecation(
        self, operation: Operation[Any], response: transport.HttpResponse
    ) -> None:
        deprecation = response.headers.get("deprecation")
        sunset = response.headers.get("sunset")
        if deprecation is None and sunset is None:
            return
        if not _claim_deprecation_slot():
            return
        LOGGER.warning(
            "Deprecated endpoint %s %s (Deprecation: %s, Sunset: %s)",
            operation.method,
            operation.path,
            deprecation,
            sunset,
        )
        self.on_deprecation(
            DeprecationNotice(
                deprecation=deprecation,
                sunset=sunset,
                link=response.headers.get("link"),
                method=operation.method,
                url=self.base_url + operation.path,
            )
        )


def json_object(response: transport.HttpResponse) -> dict[str, Any] | None:
    """The body as a dict, or ``None`` when it is not JSON or not a JSON object."""
    try:
        body: Any = response.json()
    except ValueError:
        return None
    return cast("dict[str, Any]", body) if isinstance(body, dict) else None


def lower_headers(response: transport.HttpResponse) -> dict[str, str]:
    """The response headers as a plain dict with lower-case names."""
    return {name.lower(): value for name, value in response.headers.items()}


def _merge_headers(base: dict[str, str], *overrides: Mapping[str, str] | None) -> dict[str, str]:
    """Overlay header mappings on ``base``. Names match case-insensitively; the last one wins."""
    merged = dict(base)
    for override in overrides:
        for name, value in (override or {}).items():
            for existing in [key for key in merged if key.lower() == name.lower()]:
                del merged[existing]
            merged[name] = value
    return merged


def _merge_query(
    query: Sequence[tuple[str, str]], extra: Mapping[str, str | int | bool] | None
) -> list[tuple[str, str]]:
    """Add ``extra`` query parameters. An extra parameter replaces a built one of the same name."""
    if not extra:
        return list(query)
    names = set(extra) | {f"{name}[]" for name in extra}
    kept = [pair for pair in query if pair[0] not in names]
    return kept + [(name, _scalar(value)) for name, value in extra.items()]


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _number(value: Any, fallback: float | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return value


def _header_seconds(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header that holds whole seconds. HTTP dates are not covered."""
    if value is None:
        return None
    text = value.strip()
    return float(int(text)) if text.isdigit() else None
