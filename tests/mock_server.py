"""An in-process mock of the Klaracase API, built on ``httpx2.MockTransport``.

It serves a conformance case's ``responses`` in order and records every request, so a test can
compare method, raw path, query, headers and body. No socket is opened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx2

API_PREFIX = "/api/v1"


@dataclass
class RecordedRequest:
    method: str
    path: str
    query: list[tuple[str, str]]
    headers: httpx2.Headers
    body: bytes

    def query_map(self) -> dict[str, str | list[str]]:
        mapped: dict[str, str | list[str]] = {}
        for name, value in self.query:
            if name.endswith("[]"):
                existing = mapped.setdefault(name, [])
                assert isinstance(existing, list)
                existing.append(value)
            else:
                mapped[name] = value
        return mapped

    def json(self) -> Any:
        return json.loads(self.body)

    def multipart(self) -> list[dict[str, str | None]]:
        content_type = self.headers["content-type"]
        raw = (
            b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + self.body
        )
        message = BytesParser(policy=policy.HTTP).parsebytes(raw)
        parts: list[dict[str, str | None]] = []
        for part in message.iter_parts():
            parts.append(
                {
                    "name": part.get_param("name", header="content-disposition"),  # type: ignore[dict-item]
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                }
            )
        return parts


@dataclass
class MockServer:
    """Serve ``responses`` in order. ``base_dir`` resolves ``body_file`` paths."""

    responses: list[dict[str, Any]]
    base_dir: Path
    repeat_last: bool = False
    requests: list[RecordedRequest] = field(default_factory=list)

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        raw_target = request.url.raw_path.decode("ascii")
        raw_path, _, raw_query = raw_target.partition("?")
        assert raw_path.startswith(API_PREFIX), raw_path
        self.requests.append(
            RecordedRequest(
                method=request.method,
                path=raw_path[len(API_PREFIX) :],
                query=parse_qsl(raw_query, keep_blank_values=True),
                headers=request.headers,
                body=request.read(),
            )
        )
        index = len(self.requests) - 1
        if index >= len(self.responses):
            if not (self.repeat_last and self.responses):
                return httpx2.Response(599, text="mock: no response left")
            index = len(self.responses) - 1
        spec = self.responses[index]
        if spec.get("drop_connection"):
            raise httpx2.RemoteProtocolError("server closed the connection", request=request)
        delay = spec.get("delay_seconds")
        read_timeout = request.extensions.get("timeout", {}).get("read")
        if delay and read_timeout is not None and delay > read_timeout:
            raise httpx2.ReadTimeout("timed out", request=request)
        return self._build(spec)

    def _build(self, spec: dict[str, Any]) -> httpx2.Response:
        headers = {name.lower(): value for name, value in spec.get("headers", {}).items()}
        if "body_file" in spec:
            path = (self.base_dir / spec["body_file"]).resolve()
            if path.suffix == ".json":
                content = path.read_bytes()
                headers.setdefault("content-type", "application/json")
            else:
                content = path.read_bytes()
        elif "body_text" in spec:
            content = spec["body_text"].encode()
        elif "body" in spec:
            content = json.dumps(spec["body"]).encode()
            headers.setdefault("content-type", "application/json")
        else:
            content = b""
        return httpx2.Response(spec["status"], headers=headers, content=content)
