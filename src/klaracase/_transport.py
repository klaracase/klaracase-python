"""The one place that imports the HTTP library.

Everything else in the package reaches the HTTP stack through this module, so the library can be
swapped again by editing this file (and the dependency line in ``pyproject.toml``).

The package uses ``httpx2``, the maintained continuation of ``httpx`` (same API, new import name).
"""

from __future__ import annotations

from typing import Any

import httpx2

Client = httpx2.Client
AsyncClient = httpx2.AsyncClient
Timeout = httpx2.Timeout
Request = httpx2.Request
HttpResponse = httpx2.Response
RequestError = httpx2.RequestError
TimeoutException = httpx2.TimeoutException
MockTransport = httpx2.MockTransport

DEFAULT_TIMEOUT = Timeout(30.0, connect=5.0)
"""30 seconds for one HTTP attempt, 5 seconds of that to open the connection."""

__all__ = [
    "DEFAULT_TIMEOUT",
    "AsyncClient",
    "Client",
    "DefaultAsyncHttpClient",
    "DefaultHttpClient",
    "HttpResponse",
    "MockTransport",
    "Request",
    "RequestError",
    "Timeout",
    "TimeoutException",
]


class DefaultHttpClient(Client):
    """A plain HTTP client with the SDK defaults, for when you only need to change a detail.

    Use it for a proxy, a custom CA bundle or a client certificate. Every argument of the
    underlying client is accepted::

        Klaracase(http_client=DefaultHttpClient(proxy="http://proxy.example:3128"))

    The SDK sets the timeout on every request, so a ``timeout`` given here is not used. Set the
    timeout with the ``timeout`` argument of the SDK client or of a single call.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        super().__init__(**kwargs)


class DefaultAsyncHttpClient(AsyncClient):
    """The async twin of :class:`DefaultHttpClient`."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        super().__init__(**kwargs)
