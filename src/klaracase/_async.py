"""The asynchronous client. Same operations as the sync client, with ``await``."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from types import TracebackType
from typing import BinaryIO, Self, TypeVar

import httpx

from . import _operations as ops
from ._core import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Core,
    DeprecationHook,
    Operation,
    Retry,
)
from .errors import DocumentFailedError, DocumentTimeoutError
from .types import (
    DOCUMENT_TERMINAL_STATUSES,
    Branch,
    CitationCheck,
    CitationCheckDocument,
    CitationDepth,
    CitationDirection,
    CitedStatute,
    CorpusCoverage,
    CorpusFacets,
    CrossTypeSearch,
    Datapackage,
    Decision,
    DecisionCitations,
    DecisionSearch,
    DocumentType,
    FacetField,
    FacetType,
    Norm,
    NormJurisdiction,
    Response,
    SearchJurisdiction,
    SearchMode,
)

T = TypeVar("T", bound=Response)


class AsyncKlaracase:
    """Asynchronous client for the Klaracase REST API v1.

    Args:
        token: A Klaracase API token. Falls back to the ``KLARACASE_API_TOKEN`` environment
            variable. A missing token raises :class:`~klaracase.ConfigurationError`.
        base_url: The API base URL.
        timeout: Seconds for one HTTP attempt.
        max_retries: How many times to retry a 429, a 503 or (GET only) a transport error.
        user_agent_suffix: Text appended to the ``User-Agent`` header.
        http_client: Your own ``httpx.AsyncClient``. The SDK then does not close it.
        on_deprecation: Called once per process when an answer carries a ``Deprecation`` or
            ``Sunset`` header. The default emits a ``DeprecationWarning``.
        sleep: Replaces ``asyncio.sleep`` for retry waits and polling. For tests.
        monotonic: Replaces ``time.monotonic``. For tests.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent_suffix: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        on_deprecation: DeprecationHook | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._core = Core.create(
            token=token,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            user_agent_suffix=user_agent_suffix,
            on_deprecation=on_deprecation,
            monotonic=monotonic,
        )
        self._owns_http = http_client is None
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self.decisions = Decisions(self)
        self.norms = Norms(self)
        self.datapackages = Datapackages(self)
        self.citation_checks = CitationChecks(self)
        self.citation_check_documents = CitationCheckDocuments(self)
        self.corpus = Corpus(self)

    async def aclose(self) -> None:
        """Close the HTTP client, unless you passed your own."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def search(
        self,
        query: str,
        *,
        jurisdiction: SearchJurisdiction | None = None,
        court: str | None = None,
        branch: Branch | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        mode: SearchMode | None = None,
        document_type: DocumentType | None = None,
        cited_norm: str | None = None,
        cited_statutes: Sequence[CitedStatute] | None = None,
        limit: int | None = None,
        bridge: bool | None = None,
    ) -> CrossTypeSearch:
        """Search statutes and decisions together (``GET /search``). Costs 1 credit."""
        return await self._execute(
            ops.cross_type_search(
                query,
                jurisdiction=jurisdiction,
                court=court,
                branch=branch,
                date_from=date_from,
                date_to=date_to,
                mode=mode,
                document_type=document_type,
                cited_norm=cited_norm,
                cited_statutes=cited_statutes,
                limit=limit,
                bridge=bridge,
            )
        )

    async def _execute(self, operation: Operation[T]) -> T:
        retries = 0
        while True:
            request = self._http.build_request(**self._core.request_kwargs(operation))
            started = self._core.monotonic()
            try:
                response = await self._http.send(request)
            except httpx.RequestError as exc:
                wait = self._core.transport_wait(operation, retries)
                if wait is None:
                    raise self._core.transport_error(exc) from exc
                await self._sleep(wait)
                retries += 1
                continue
            outcome = self._core.evaluate(operation, response, retries, started)
            if isinstance(outcome, Retry):
                await self._sleep(outcome.wait)
                retries += 1
                continue
            return outcome


class Decisions:
    """Court decisions: ``client.decisions``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def search(
        self,
        query: str,
        *,
        court: str | None = None,
        branch: Branch | None = None,
        document_type: DocumentType | None = None,
        cited_norm: str | None = None,
        cited_statutes: Sequence[CitedStatute] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        mode: SearchMode | None = None,
        limit: int | None = None,
        page: int | None = None,
        bridge: bool | None = None,
    ) -> DecisionSearch:
        """Search decisions (``GET /decisions/search``). Costs 1 credit."""
        return await self._client._execute(
            ops.decisions_search(
                query,
                court=court,
                branch=branch,
                document_type=document_type,
                cited_norm=cited_norm,
                cited_statutes=cited_statutes,
                date_from=date_from,
                date_to=date_to,
                mode=mode,
                limit=limit,
                page=page,
                bridge=bridge,
            )
        )

    async def get(
        self,
        id: str,
        *,
        max_chars: int | None = None,
        rn_from: int | None = None,
        rn_to: int | None = None,
        section: str | None = None,
        court: str | None = None,
        date: str | None = None,
    ) -> Decision:
        """Read one decision (``GET /decisions/{id}``). Costs 1 credit.

        ``id`` is a UUID, an Aktenzeichen or an ECLI. The SDK encodes it as one path segment.
        """
        return await self._client._execute(
            ops.decision_get(
                id,
                max_chars=max_chars,
                rn_from=rn_from,
                rn_to=rn_to,
                section=section,
                court=court,
                date=date,
            )
        )

    async def citations(
        self,
        id: str,
        *,
        direction: CitationDirection | None = None,
        depth: CitationDepth | None = None,
        court: str | None = None,
        date: str | None = None,
        page: int | None = None,
    ) -> DecisionCitations:
        """Follow the citations of one decision (``GET /decisions/{id}/citations``). 2 credits."""
        return await self._client._execute(
            ops.decision_citations(
                id, direction=direction, depth=depth, court=court, date=date, page=page
            )
        )


class Norms:
    """Statute norms: ``client.norms``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def get(self, reference: str, *, jurisdiction: NormJurisdiction | None = None) -> Norm:
        """Read one norm, for example ``"§ 535 BGB"`` (``GET /norms/{reference}``). 1 credit."""
        return await self._client._execute(ops.norm_get(reference, jurisdiction=jurisdiction))


class Datapackages:
    """Data packages: ``client.datapackages``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def create(
        self,
        ids: Sequence[str],
        *,
        include_citations: bool | None = None,
        full_text: bool | None = None,
        max_chars: int | None = None,
    ) -> Datapackage:
        """Bundle 1 to 10 decisions and their citations (``POST /datapackages``). 5 credits."""
        return await self._client._execute(
            ops.datapackage_create(
                ids,
                include_citations=include_citations,
                full_text=full_text,
                max_chars=max_chars,
            )
        )


class CitationChecks:
    """Citation checks: ``client.citation_checks``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def create(
        self,
        *,
        text: str | None = None,
        document_id: str | None = None,
        reference_date: str | None = None,
    ) -> CitationCheck:
        """Check the citations in a text or in a ready upload (``POST /citation-checks``).

        Pass exactly one of ``text`` and ``document_id``. The answer is the finished run. The
        price is by length, from 2 credits.
        """
        return await self._client._execute(
            ops.citation_check_create(
                text=text, document_id=document_id, reference_date=reference_date
            )
        )

    async def get(self, run_id: str) -> CitationCheck:
        """Read a run back by its id (``GET /citation-checks/{run}``). Free."""
        return await self._client._execute(ops.citation_check_get(run_id))


class CitationCheckDocuments:
    """Uploads for citation checks: ``client.citation_check_documents``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def upload(
        self,
        file: bytes | BinaryIO,
        *,
        filename: str,
        content_type: str,
    ) -> CitationCheckDocument:
        """Upload a PDF, DOCX, Markdown or text file (``POST /citation-check-documents``).

        The answer is a receipt with status ``uploaded``. Uploading is free.
        """
        data = ops.read_file(file)
        return await self._client._execute(
            ops.document_upload(data, filename=filename, content_type=content_type)
        )

    async def get(self, document_id: str) -> CitationCheckDocument:
        """Read the receipt of an upload (``GET /citation-check-documents/{document}``). Free."""
        return await self._client._execute(ops.document_get(document_id))

    async def wait_until_ready(
        self,
        document_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> CitationCheckDocument:
        """Poll until the upload is ``ready`` and return its receipt.

        Raises:
            DocumentFailedError: The upload ended with status ``failed``.
            DocumentTimeoutError: The upload was not ready within ``timeout`` seconds.
        """
        core = self._client._core
        started = core.monotonic()
        while True:
            document = await self.get(document_id)
            if document.status == "failed":
                raise DocumentFailedError(document)
            if document.status in DOCUMENT_TERMINAL_STATUSES:
                return document
            remaining = timeout - (core.monotonic() - started)
            if remaining <= 0:
                raise DocumentTimeoutError(document, timeout)
            await self._client._sleep(min(poll_interval, remaining))


class Corpus:
    """Corpus statistics, free: ``client.corpus``."""

    def __init__(self, client: AsyncKlaracase) -> None:
        self._client = client

    async def coverage(
        self, *, branch: Branch | None = None, top: int | None = None
    ) -> CorpusCoverage:
        """Report what the corpus covers (``GET /corpus/coverage``). Free."""
        return await self._client._execute(ops.corpus_coverage(branch=branch, top=top))

    async def facets(
        self,
        field: FacetField,
        *,
        type: FacetType | None = None,
        norm: str | None = None,
        prefix: str | None = None,
    ) -> CorpusFacets:
        """Count the values of one field (``GET /corpus/facets/{field}``). Free.

        ``norm`` is required for ``field="cited_norms"``.
        """
        return await self._client._execute(
            ops.corpus_facets(field, type=type, norm=norm, prefix=prefix)
        )
