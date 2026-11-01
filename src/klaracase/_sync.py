"""The synchronous client."""

from __future__ import annotations

import copy
import datetime
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, Self, TypeVar, overload

from . import _operations as ops
from . import _transport as transport
from ._core import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Core,
    DeprecationHook,
    Operation,
    RequestOptions,
    Retry,
    replace_options,
    request_options,
)
from ._transport import Timeout
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


class Klaracase:
    """Synchronous client for the Klaracase REST API v1.

    Every call method also takes the keyword-only options ``timeout``, ``extra_headers`` and
    ``extra_query``. They apply to that call only.

    Args:
        token: A Klaracase API token. Falls back to the ``KLARACASE_API_TOKEN`` environment
            variable. A missing token raises :class:`~klaracase.ConfigurationError`.
        base_url: The API base URL.
        timeout: Seconds for one HTTP attempt, or a ``Timeout`` for a finer split. The default is
            30 seconds with 5 seconds to connect.
        max_retries: How many times to retry a 429, a 503 or (GET only) a transport error.
        user_agent_suffix: Text appended to the ``User-Agent`` header.
        http_client: Your own ``httpx2.Client``. The SDK then does not close it, and it sets the
            timeout on every request, so the timeout of your client is not used. Use
            :class:`~klaracase.DefaultHttpClient` to change only a proxy or a certificate.
        on_deprecation: Called once per process when an answer carries a ``Deprecation`` or
            ``Sunset`` header. The default emits a ``DeprecationWarning``.
        sleep: Replaces ``time.sleep`` for retry waits and polling. For tests.
        monotonic: Replaces ``time.monotonic``. For tests.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent_suffix: str | None = None,
        http_client: transport.Client | None = None,
        on_deprecation: DeprecationHook | None = None,
        sleep: Callable[[float], None] | None = None,
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
        self._http = http_client if http_client is not None else transport.Client()
        self._sleep = sleep if sleep is not None else time.sleep
        self._bind_resources()

    def _bind_resources(self) -> None:
        self.decisions = Decisions(self)
        self.norms = Norms(self)
        self.datapackages = Datapackages(self)
        self.citation_checks = CitationChecks(self)
        self.citation_check_documents = CitationCheckDocuments(self)
        self.corpus = Corpus(self)

    def __repr__(self) -> str:
        return (
            f"Klaracase(base_url={self._core.base_url!r}, timeout={self._core.timeout!r}, "
            f"max_retries={self._core.max_retries}, token=<redacted>)"
        )

    def close(self) -> None:
        """Close the HTTP client, unless you passed your own."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def with_options(
        self,
        *,
        timeout: float | Timeout | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Self:
        """Return a new client with some settings replaced, sharing this client's connections.

        Args:
            timeout: Seconds or a ``Timeout`` for every call of the new client.
            max_retries: Retries for every call of the new client.
            extra_headers: Headers added to every call. They add to the headers of this client.

        The new client does not own the connection pool: closing it does nothing. Close the
        original client when you are done with both.
        """
        clone = copy.copy(self)
        clone._core = self._core.with_options(
            timeout=timeout, max_retries=max_retries, extra_headers=extra_headers
        )
        clone._owns_http = False
        clone._bind_resources()
        return clone

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> Response:
        """Send a GET to any path below the base URL, with retries, and return a ``Response``.

        Use it for an endpoint this SDK version does not wrap yet. The path is used as given:
        encode path segments yourself. The answer has ``raw``, ``extra`` (all keys except
        ``api_version``, ``changelog_url`` and ``credits``), ``credits`` and ``meta``.

        Args:
            path: The path below the base URL, starting with ``/``, for example
                ``/corpus/coverage``.
            params: Query parameters. ``None`` values are not sent. A list is sent as ``name[]``.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._execute(
            ops.raw_get(path, params), request_options(timeout, extra_headers, extra_query)
        )

    def post(
        self,
        path: str,
        json: Mapping[str, Any] | None = None,
        *,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> Response:
        """Send a POST with a JSON body to any path below the base URL and return a ``Response``.

        A POST is retried on 429 and 503 only, never after a dropped connection.

        Args:
            path: The path below the base URL, starting with ``/``.
            json: The JSON body.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._execute(
            ops.raw_post(path, json), request_options(timeout, extra_headers, extra_query)
        )

    def search(
        self,
        query: str,
        *,
        jurisdiction: SearchJurisdiction | None = None,
        court: str | None = None,
        branch: Branch | None = None,
        date_from: str | datetime.date | None = None,
        date_to: str | datetime.date | None = None,
        mode: SearchMode | None = None,
        document_type: DocumentType | None = None,
        cited_norm: str | None = None,
        cited_statutes: Sequence[CitedStatute | str] | None = None,
        limit: int | None = None,
        bridge: bool | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CrossTypeSearch:
        """Search statutes and decisions together (``GET /search``). Costs 1 credit.

        Args:
            query: German legal-concept phrasing, 2 to 500 characters. Longer input is rejected.
            jurisdiction: ``DE``, ``EU`` or ``XI``. Narrows the laws section only.
            court: Court name filter on the decisions section, for example ``BGH``.
            branch: Gerichtsbarkeit (court branch). It names the court jurisdiction, not the legal
                subject area. ``patent`` is the Bundespatentgericht alone.
            date_from: Earliest decision date, inclusive. A string ``YYYY-MM-DD`` or a date.
            date_to: Latest decision date, inclusive, not earlier than ``date_from``.
            mode: ``hybrid`` (default), ``keyword`` (not reranked) or ``semantic``.
            document_type: Restrict the decisions section to one document type.
            cited_norm: Restrict the decisions section to decisions whose Normenkette cites this
                statute, for example ``§ 906 BGB``. Subdivisions nest.
            cited_statutes: Any section of these statutes, for example ``["StGB", "StPO"]``.
            limit: Maximum results per section (default 5, capped at 10 by the server).
            bridge: Whether the server may add curated legal-register terms to your query
                (default true). False searches your literal query.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._execute(
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
            ),
            request_options(timeout, extra_headers, extra_query),
        )

    def _execute(self, operation: Operation[T], options: RequestOptions | None = None) -> T:
        if options is not None:
            operation = replace_options(operation, options)
        retries = 0
        while True:
            self._core.log_attempt(operation, retries)
            request = self._http.build_request(**self._core.request_kwargs(operation))
            started = self._core.monotonic()
            try:
                response = self._http.send(request)
            except transport.RequestError as exc:
                wait = self._core.transport_wait(operation, retries, exc)
                if wait is None:
                    raise self._core.transport_error(exc) from exc
                self._sleep(wait)
                retries += 1
                continue
            outcome = self._core.evaluate(operation, response, retries, started)
            if isinstance(outcome, Retry):
                self._sleep(outcome.wait)
                retries += 1
                continue
            return outcome


class Decisions:
    """Court decisions: ``client.decisions``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    def search(
        self,
        query: str,
        *,
        court: str | None = None,
        branch: Branch | None = None,
        document_type: DocumentType | None = None,
        cited_norm: str | None = None,
        cited_statutes: Sequence[CitedStatute | str] | None = None,
        date_from: str | datetime.date | None = None,
        date_to: str | datetime.date | None = None,
        mode: SearchMode | None = None,
        limit: int | None = None,
        page: int | None = None,
        bridge: bool | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> DecisionSearch:
        """Search decisions (``GET /decisions/search``). Costs 1 credit.

        Paging and the same search again this month cost nothing more.

        Args:
            query: German legal-concept phrasing, for example ``Widerrufsrecht
                Fernabsatzvertrag Wertersatz Verbraucher``. 2 to 500 characters.
            court: Court filter on the indexed court name. The vocabulary is mixed and
                chamber-level; ``corpus.facets("court_name")`` lists the values.
            branch: Gerichtsbarkeit (court branch) filter. It names the court jurisdiction that
                decided the case, not the legal subject area.
            document_type: Restrict to one decision document type.
            cited_norm: Restrict to decisions whose Normenkette cites this statute, for example
                ``§ 906 BGB``. One canonical section token; subdivisions nest.
            cited_statutes: Any section of these statutes, for example ``["StGB", "StPO"]``.
            date_from: Earliest decision date, inclusive. A string ``YYYY-MM-DD`` or a date. A
                scanned decision can carry a wrong stored date.
            date_to: Latest decision date, inclusive, not earlier than ``date_from``.
            mode: ``hybrid`` (default), ``keyword`` (all terms, not reranked) or ``semantic``.
            limit: Maximum results. Default 20, which is also the cap.
            page: 1-based page number, up to 10, for results past the first page.
            bridge: Whether the server may add curated legal-register terms before retrieval
                (default true). The outcome is in ``query_expansion``.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
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
            ),
            request_options(timeout, extra_headers, extra_query),
        )

    def get(
        self,
        id: str,
        *,
        max_chars: int | None = None,
        rn_from: int | None = None,
        rn_to: int | None = None,
        section: str | None = None,
        court: str | None = None,
        date: str | datetime.date | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> Decision:
        """Read one decision (``GET /decisions/{id}``). Costs 1 credit per decision per month.

        Reading it again, in any slice, costs nothing more. The SDK encodes ``id`` as one path
        segment.

        Args:
            id: A UUID, an Aktenzeichen or an ECLI.
            max_chars: Maximum characters of text to return (default 40000, minimum 500).
            rn_from: First Randnummer to return. Whole chunks come back, so the served span is
                in ``returned_range``.
            rn_to: Highest Randnummer to return, inclusive. Not below ``rn_from``.
            section: A named section instead of the whole text: Tenor, Leitsatz, Tatbestand or
                Gründe, case-insensitive. ``available_sections`` lists the sections a decision
                has.
            court: Disambiguates an Aktenzeichen ``id``: the court short form, for example
                ``BGH``. Ignored for UUIDs.
            date: Disambiguates an Aktenzeichen ``id``: the decision date, ``YYYY-MM-DD`` or a
                date.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.decision_get(
                id,
                max_chars=max_chars,
                rn_from=rn_from,
                rn_to=rn_to,
                section=section,
                court=court,
                date=date,
            ),
            request_options(timeout, extra_headers, extra_query),
        )

    def citations(
        self,
        id: str,
        *,
        direction: CitationDirection | None = None,
        depth: CitationDepth | None = None,
        court: str | None = None,
        date: str | datetime.date | None = None,
        page: int | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> DecisionCitations:
        """Follow the citations of one decision (``GET /decisions/{id}/citations``).

        Costs 2 credits per decision, direction and depth per month. Paging is free.

        Args:
            id: A UUID, an Aktenzeichen or an ECLI.
            direction: ``outgoing`` (decisions this one cites), ``incoming`` (decisions citing
                this one) or ``both`` (default).
            depth: 1 (default) for direct neighbours, 2 for neighbours of neighbours, capped at
                50 distinct decisions and served as a bounded sample.
            court: Disambiguates an Aktenzeichen ``id``, for example ``BVerfG`` or ``OLG Hamm``.
            date: Disambiguates an Aktenzeichen ``id``: the decision date.
            page: 1-based page over the source decision's neighbour lists, 25 per direction, up
                to page 20. Defined at depth 1 only.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.decision_citations(
                id, direction=direction, depth=depth, court=court, date=date, page=page
            ),
            request_options(timeout, extra_headers, extra_query),
        )


class Norms:
    """Statute norms: ``client.norms``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    def get(
        self,
        reference: str,
        *,
        jurisdiction: NormJurisdiction | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> Norm:
        """Read one norm (``GET /norms/{reference}``). Costs 1 credit per norm per month.

        Args:
            reference: The citation, for example ``§ 535 BGB`` or ``Art. 6 DSGVO``.
            jurisdiction: ``DE`` or ``EU``. Only read when the abbreviation is ambiguous.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.norm_get(reference, jurisdiction=jurisdiction),
            request_options(timeout, extra_headers, extra_query),
        )


class Datapackages:
    """Data packages: ``client.datapackages``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    def create(
        self,
        ids: Sequence[str],
        *,
        include_citations: bool | None = None,
        full_text: bool | None = None,
        max_chars: int | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> Datapackage:
        """Bundle 1 to 10 decisions and their citations (``POST /datapackages``). 5 credits.

        Args:
            ids: 1 to 10 decision ids. Order matters: the response budget drops decisions from
                the end. Duplicates collapse into one decision.
            include_citations: Include each decision's outgoing citation edges (default true).
            full_text: Serve whole judgments instead of excerpts of about 700 characters
                (default false). This is heavy on tokens.
            max_chars: Per-decision text cap when ``full_text`` is true (default 60000, minimum
                500, maximum 200000). A ceiling, not a guarantee.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.datapackage_create(
                ids,
                include_citations=include_citations,
                full_text=full_text,
                max_chars=max_chars,
            ),
            request_options(timeout, extra_headers, extra_query),
        )


class CitationChecks:
    """Citation checks: ``client.citation_checks``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    @overload
    def create(
        self,
        *,
        text: str,
        reference_date: str | datetime.date | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheck: ...

    @overload
    def create(
        self,
        *,
        document_id: str,
        reference_date: str | datetime.date | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheck: ...

    def create(
        self,
        *,
        text: str | None = None,
        document_id: str | None = None,
        reference_date: str | datetime.date | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheck:
        """Check the citations in a text or in a ready upload (``POST /citation-checks``).

        The answer is the finished run. Check ``status`` before you trust ``findings``: a run
        can end ``rejected`` or ``failed``. The price is by length, from 2 credits; the same
        text again this month costs nothing more.

        Args:
            text: The German legal text, 50 to 20000 characters. It must show at least two of five
                legal-signal categories. Offsets in the answer are Unicode code point offsets
                into this exact string. Pass this or ``document_id``, never both.
            document_id: The id of an upload whose ``status`` is ``ready``. The check consumes
                the upload.
            reference_date: Optional document date, ``YYYY-MM-DD`` or a date. It applies to
                every statute citation whose own sentence names no date. It changes no verdict.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.citation_check_create(
                text=text, document_id=document_id, reference_date=reference_date
            ),
            request_options(timeout, extra_headers, extra_query),
        )

    def get(
        self,
        run_id: str,
        *,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheck:
        """Read a run back by its id (``GET /citation-checks/{run}``). Free.

        Args:
            run_id: The ``id`` of a run.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.citation_check_get(run_id), request_options(timeout, extra_headers, extra_query)
        )


class CitationCheckDocuments:
    """Uploads for citation checks: ``client.citation_check_documents``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    def upload(
        self,
        file: Path | str | bytes | BinaryIO,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheckDocument:
        """Upload a PDF, DOCX, Markdown or text file (``POST /citation-check-documents``).

        The answer is a receipt with status ``uploaded``. Uploading is free. Poll with
        ``wait_until_ready``, then pass the id to ``citation_checks.create``.

        Args:
            file: A path (``Path`` or ``str``), the bytes, or a binary file object. A file
                object is read once, so a retry sends the same bytes. Up to 25 MB.
            filename: The file name to send. Defaults to the name of the path or file object.
                Required for bytes.
            content_type: The media type. Inferred from the file name when not given.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        name, media_type = ops.upload_name(file, filename, content_type)
        data = ops.read_file(file)
        return self._client._execute(
            ops.document_upload(data, filename=name, content_type=media_type),
            request_options(timeout, extra_headers, extra_query),
        )

    def get(
        self,
        document_id: str,
        *,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CitationCheckDocument:
        """Read the receipt of an upload (``GET /citation-check-documents/{document}``). Free.

        Args:
            document_id: The ``id`` of an upload.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.document_get(document_id), request_options(timeout, extra_headers, extra_query)
        )

    def wait_until_ready(
        self,
        document_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> CitationCheckDocument:
        """Poll until the upload is ``ready`` and return its receipt.

        Args:
            document_id: The ``id`` of an upload.
            poll_interval: Seconds between two polls.
            timeout: Seconds to wait in total.

        Raises:
            DocumentFailedError: The upload ended with status ``failed``.
            DocumentTimeoutError: The upload was not ready within ``timeout`` seconds.
        """
        core = self._client._core
        started = core.monotonic()
        while True:
            document = self.get(document_id)
            if document.status == "failed":
                raise DocumentFailedError(document)
            if document.status in DOCUMENT_TERMINAL_STATUSES:
                return document
            remaining = timeout - (core.monotonic() - started)
            if remaining <= 0:
                raise DocumentTimeoutError(document, timeout)
            self._client._sleep(min(poll_interval, remaining))


class Corpus:
    """Corpus statistics, free: ``client.corpus``."""

    def __init__(self, client: Klaracase) -> None:
        self._client = client

    def coverage(
        self,
        *,
        branch: Branch | None = None,
        top: int | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CorpusCoverage:
        """Report what the corpus covers (``GET /corpus/coverage``). Free.

        Args:
            branch: Scope the report to one Gerichtsbarkeit slug. A branch is a court
                jurisdiction, not a legal subject area. Omit it to report every branch.
            top: Cap on the per-court rows, busiest first (default 20, maximum 100). The branch
                rollup is never capped.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.corpus_coverage(branch=branch, top=top),
            request_options(timeout, extra_headers, extra_query),
        )

    def facets(
        self,
        field: FacetField,
        *,
        type: FacetType | None = None,
        norm: str | None = None,
        prefix: str | None = None,
        timeout: float | Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_query: Mapping[str, str | int | bool] | None = None,
    ) -> CorpusFacets:
        """Count the values of one field (``GET /corpus/facets/{field}``). Free.

        Args:
            field: The field to count: ``court_name``, ``court_branch``, ``document_type``,
                ``jurisdiction``, ``law_type`` or ``cited_norms``.
            type: Restrict the counts to ``decision`` or ``law``. Ignored for ``cited_norms``.
            norm: Required with ``field="cited_norms"``, ignored otherwise: the norm whose
                family to list, for example ``§ 543 BGB``. It is echoed back.
            prefix: Case-insensitive prefix filter on the facet value. A trailing space counts.
            timeout: Seconds or a ``Timeout`` for this call only.
            extra_headers: Extra headers for this call only.
            extra_query: Extra query parameters for this call only.
        """
        return self._client._execute(
            ops.corpus_facets(field, type=type, norm=norm, prefix=prefix),
            request_options(timeout, extra_headers, extra_query),
        )
