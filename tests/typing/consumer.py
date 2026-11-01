"""What a user's type checker must accept and must reject.

mypy (strict) and pyright (strict) both check this file in CI; it is never run. A line with
``# type: ignore[...]`` is a call the types must refuse. Both checkers report an ignore that is
not needed, so a refusal that stops working turns the check red.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, assert_type

import klaracase
from klaracase import (
    AsyncKlaracase,
    CitationCheck,
    Credits,
    Decision,
    DecisionSearch,
    Finding,
    Klaracase,
    KlaracaseError,
    Norm,
    RateLimitError,
    SearchHit,
    Timeout,
)
from klaracase.agents import dispatch, tool_definitions


def sync_usage(client: Klaracase, text: str) -> None:
    found = client.decisions.search(
        "Untreue",
        court="BGH",
        branch="ordentlich",
        date_from=datetime.date(2020, 1, 1),
        date_to="2026-10-01",
        cited_statutes=["StGB", "UWG"],
        timeout=Timeout(30, connect=5),
        extra_headers={"X-Team": "a"},
        extra_query={"flag": True},
    )
    assert_type(found, DecisionSearch)
    for hit in found.results:
        assert_type(hit, SearchHit)
        assert_type(hit.id, str)
        assert_type(hit.court, str | None)
        assert_type(hit.snippets[0].rn, int | None)
    assert_type(found.credits, Credits)
    assert_type(found.credits.cost, int | None)
    assert_type(found.meta.status, int)
    assert_type(found.meta.headers, dict[str, str])
    assert_type(found.to_dict(), dict[str, Any])

    decision = client.decisions.get("1 StR 185/01", section="Leitsatz")
    assert_type(decision, Decision)
    assert_type(decision.ecli, str | None)
    assert_type(decision.available_sections, list[str])

    norm = client.norms.get("§ 535 BGB")
    assert_type(norm, Norm)
    if norm.norm is not None:
        assert_type(norm.norm.text, str | None)

    run = client.citation_checks.create(text=text, reference_date=datetime.date(2026, 10, 1))
    assert_type(run, CitationCheck)
    by_document = client.citation_checks.create(document_id="d1")
    assert_type(by_document, CitationCheck)
    uploaded = client.citation_check_documents.upload(Path("brief.pdf"))
    assert_type(uploaded.id, str)
    from_file = client.citation_checks.create_from_file(Path("brief.pdf"), wait_timeout=60.0)
    assert_type(from_file.verdict_counts, dict[str, int])
    for finding in run.findings:
        assert_type(finding, Finding)
        assert_type(finding.excerpt(text), str | None)
        if finding.verdict == "not_found":
            print(finding.canonical)
    assert_type(run.by_verdict(), dict[str, list[Finding]])

    for page in client.decisions.iter_pages("Untreue", max_pages=3, court="BGH"):
        assert_type(page, DecisionSearch)
    for graph in client.decisions.iter_citation_pages("1 StR 185/01", max_pages=2, depth=1):
        assert_type(graph.references[0].corpus, klaracase.CorpusRef | None)

    raw = client.get("/corpus/coverage", {"top": 3})
    assert_type(raw.raw, dict[str, Any])
    other = client.with_options(max_retries=0, extra_headers={"X-Team": "b"})
    assert_type(other, Klaracase)

    try:
        client.corpus.coverage()
    except RateLimitError as error:
        assert_type(error.retry_after_seconds, float | None)
        assert_type(error.retryable, bool)
    except KlaracaseError as error:
        assert_type(error.status_code, int | None)
        assert_type(error.body, dict[str, Any] | None)

    tools = tool_definitions(["search_decisions"], format="anthropic")
    print(tools, dispatch(client, "get_norm", {"reference": "§ 535 BGB"}))


async def async_usage(client: AsyncKlaracase) -> None:
    result = await client.decisions.search("Untreue")
    assert_type(result.results, list[SearchHit])
    async for page in client.decisions.iter_pages("Untreue", max_pages=2):
        assert_type(page, DecisionSearch)
    run = await client.citation_checks.create(text="x" * 60)
    assert_type(run.findings, list[Finding])
    await client.aclose()


def refusals(client: Klaracase) -> None:
    client.citation_checks.create(text="a", document_id="b")  # type: ignore[call-overload]
    client.citation_checks.create()  # type: ignore[call-overload]
    client.decisions.iter_pages("q")  # type: ignore[call-arg]
    client.decisions.iter_pages("q", max_pages=2, page=2)  # type: ignore[call-arg]
    client.decisions.search("q", branch="nonsense")  # type: ignore[arg-type]
    client.decisions.search("q", date_from=20260101)  # type: ignore[arg-type]
    hit = client.decisions.search("q").results[0]
    print(hit.not_a_field)  # type: ignore[attr-defined]
    run = client.citation_checks.create(text="a")
    run.id = "other"  # type: ignore[misc]
