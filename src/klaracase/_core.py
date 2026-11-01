"""The transport core shared by the sync and the async client.

Everything that is not input or output lives here: configuration, request building, the retry
policy and problem parsing. ``Klaracase`` and ``AsyncKlaracase`` only move bytes and sleep.
"""

from __future__ import annotations

import os
import platform
import random
import threading
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from urllib.parse import quote, urlsplit

from . import _transport as transport
from ._version import __version__
from .errors import (
    ApiError,
    ConfigurationError,
    KlaracaseError,
    KlaracaseTimeoutError,
    RateLimitError,
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
UNKNOWN_CODE = "unknown"

T = TypeVar("T", bound=Response)

DeprecationHook = Callable[[DeprecationNotice], None]


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
            pairs.extend((f"{name}[]", _scalar(item)) for item in value)
            continue
        pairs.append((name, _scalar(value)))
    return pairs


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


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

    token: str
    base_url: str
    timeout: float | transport.Timeout
    max_retries: int
    user_agent: str
    on_deprecation: DeprecationHook
    monotonic: Callable[[], float]
    uniform: Callable[[float, float], float] = field(default=random.uniform)

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
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ConfigurationError("max_retries must be an integer of 0 or more.")
        if not isinstance(timeout, transport.Timeout) and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
        ):
            raise ConfigurationError("timeout must be a number of seconds above 0 or a Timeout.")
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
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        kwargs: dict[str, Any] = {
            "method": operation.method,
            "url": self.base_url + operation.path,
            "headers": headers,
            "timeout": self.timeout,
        }
        if operation.query:
            kwargs["params"] = list(operation.query)
        if operation.json_body is not None:
            kwargs["json"] = operation.json_body
        if operation.files is not None:
            kwargs["files"] = dict(operation.files)
        return kwargs

    def backoff(self, retries_so_far: int) -> float:
        """Exponential backoff with full jitter: 0.5 s, 1 s, 2 s, ... capped at 8 s."""
        ceiling = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2**retries_so_far))
        return self.uniform(0.0, ceiling)

    def transport_wait(self, operation: Operation[Any], retries_so_far: int) -> float | None:
        """Seconds to wait before retrying after a transport error, or ``None`` to give up.

        Only GET is retried: a POST whose connection dropped may have run.
        """
        if operation.method != "GET" or retries_so_far >= self.max_retries:
            return None
        return self.backoff(retries_so_far)

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
        self._surface_deprecation(operation, response)
        if response.is_success:
            return self._parse_success(operation, response, duration)
        error = self.error_from_response(response)
        wait = self._retry_wait(response, error, retries_so_far)
        if wait is None:
            raise error
        return Retry(wait)

    def _parse_success(
        self, operation: Operation[T], response: transport.HttpResponse, duration: float
    ) -> T:
        release = response.headers.get("x-klaracase-api-release")
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise ApiError(
                "The API answered with a body that is not a JSON object.",
                status=response.status_code,
                code=UNKNOWN_CODE,
                detail=response.text[:DETAIL_LIMIT],
                api_release=release,
            )
        meta = ResponseMeta(
            status=response.status_code, api_release=release, request_duration=duration
        )
        return operation.response_cls.from_body(body, meta)

    def error_from_response(self, response: transport.HttpResponse) -> KlaracaseError:
        """Build the error class that the HTTP status decides."""
        status = response.status_code
        release = response.headers.get("x-klaracase-api-release")
        cls = error_class_for_status(status)
        text = response.text
        try:
            body = response.json()
        except ValueError:
            body = None
        header_wait = _header_seconds(response.headers.get("retry-after"))
        if isinstance(body, dict) and isinstance(body.get("code"), str):
            standard = {"type", "title", "detail", "status", "code"}
            kwargs: dict[str, Any] = {
                "type": _optional_str(body.get("type")),
                "title": _optional_str(body.get("title")),
                "detail": _optional_str(body.get("detail")),
                "code": body["code"],
                "status": status,
                "api_release": release,
                "extra": {k: v for k, v in body.items() if k not in standard},
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
        if error.code == "volume_cap":
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
        self.on_deprecation(
            DeprecationNotice(
                deprecation=deprecation,
                sunset=sunset,
                link=response.headers.get("link"),
                method=operation.method,
                url=self.base_url + operation.path,
            )
        )


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
