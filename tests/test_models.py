"""The typed response model: tolerant decoding, extra at every depth, identity keys."""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

import klaracase
from klaracase import (
    CitationCheck,
    CorpusCoverage,
    CorpusFacets,
    Credits,
    Decision,
    DecisionSearch,
    Finding,
    Norm,
    ResponseShapeError,
)

EXAMPLES = Path(__file__).parent / "fixtures" / "examples"


def load(name: str) -> dict[str, Any]:
    body = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def test_a_response_is_nested_at_every_level() -> None:
    run = CitationCheck.from_dict(load("citation-checks.show.json"))
    finding = run.findings[0]
    assert isinstance(finding, Finding)
    assert finding.verdict == "verified_corpus"
    assert finding.matched_decision is not None
    assert finding.matched_decision.ecli == "ECLI:DE:BGH:2001:151101U1STR185.01.0"
    assert finding.check_scope is not None
    assert finding.check_scope.article_text_read is False
    assert finding.evidence is not None
    assert finding.evidence.match_strength == "exact"
    assert run.progress is not None
    assert run.progress.citations_total == 2
    assert run.extraction is not None
    assert run.extraction.detected == 2


def test_unknown_keys_land_in_extra_at_every_depth() -> None:
    body = load("citation-checks.show.json")
    body["top_future"] = 1
    body["findings"][0]["evidence"]["deep_future"] = {"x": [1]}
    body["progress"]["progress_future"] = True
    run = CitationCheck.from_dict(body)
    assert run.extra == {"top_future": 1}
    assert run.findings[0].evidence is not None
    assert run.findings[0].evidence.extra == {"deep_future": {"x": [1]}}
    assert run.progress is not None
    assert run.progress.extra == {"progress_future": True}
    assert run.to_dict() == body


def test_a_wrong_typed_value_never_raises() -> None:
    body = load("decisions.search.json")
    body["page"] = "two"
    body["total_available"] = [1]
    body["results"] = {"not": "a list"}
    body["frequently_cited_by_results"] = "x"
    body["credits"] = "free"
    result = DecisionSearch.from_dict(body)
    assert result.page is None
    assert result.total_available is None
    assert result.results == []
    assert result.frequently_cited_by_results == []
    assert result.credits == Credits()
    assert result.raw["page"] == "two"


def test_a_list_drops_items_of_the_wrong_type_and_keeps_the_rest() -> None:
    body = load("decisions.search.json")
    body["results"] = [body["results"][0], "junk", 7, None]
    body["results"][0]["snippets"] = [{"text": "a", "rn": "x"}, 5]
    result = DecisionSearch.from_dict(body)
    assert len(result.results) == 1
    assert [(s.text, s.rn) for s in result.results[0].snippets] == [("a", None)]


def test_booleans_are_not_integers() -> None:
    body = load("decisions.search.json")
    body["limit"] = True
    body["truncated"] = 1
    result = DecisionSearch.from_dict(body)
    assert result.limit is None
    assert result.truncated is None


def test_collections_default_empty_and_objects_default_none() -> None:
    result = DecisionSearch.from_dict({})
    assert result.results == []
    assert result.total_available is None
    assert result.query_expansion is None
    assert result.credits == Credits(metered=None, cost=None, credits_remaining=None)
    assert Norm.from_dict({"reference": "§ 1 BGB"}).requested_qualifiers == []
    assert CorpusFacets.from_dict({"field": "court_name"}).values == {}


@pytest.mark.parametrize(
    ("cls", "body", "path"),
    [
        (Decision, {}, "id"),
        (Decision, {"id": 5}, "id"),
        (Norm, {"requested_reference": "x"}, "reference"),
        (CorpusFacets, {"values": {}}, "field"),
        (CitationCheck, {"id": "r", "findings": [{"canonical": "x"}]}, "findings[0].id"),
        (DecisionSearch, {"results": [{"title": "x"}]}, "results[0].id"),
    ],
)
def test_a_missing_identity_key_raises_a_response_shape_error(
    cls: Any, body: dict[str, Any], path: str
) -> None:
    with pytest.raises(ResponseShapeError) as caught:
        cls.from_dict(body)
    assert caught.value.path == path
    assert isinstance(caught.value, klaracase.KlaracaseError)
    assert caught.value.code == "response_shape"


def test_the_wire_key_from_maps_to_from_underscore() -> None:
    coverage = CorpusCoverage.from_dict(load("corpus.coverage.json"))
    assert coverage.coverage_ranges is not None
    first = coverage.coverage_ranges.ranges[0]
    assert first.from_ == "1950-10-02"
    assert first.extra == {}
    assert "from" not in dataclasses.asdict(first)


def test_credits_is_always_a_credits() -> None:
    assert Decision.from_dict({"id": "d1"}).credits.cost is None
    assert CorpusCoverage.from_dict(load("corpus.coverage.json")).credits.cost == 0


def test_decision_lifts_ecli_and_document_type() -> None:
    decision = Decision.from_dict(load("decisions.show.json"))
    assert decision.ecli == "ECLI:DE:BGH:2001:151101U1STR185.01.0"
    assert decision.document_type == "Urteil"
    bare = Decision.from_dict({"id": "d"})
    assert (bare.ecli, bare.document_type) == (None, None)


def test_finding_excerpt_slices_code_points() -> None:
    text = "😀 § 266 StGB"
    finding = Finding(id="f", start_offset=2, end_offset=len(text))
    assert finding.excerpt(text) == "§ 266 StGB"
    assert Finding(id="f").excerpt(text) is None


def test_by_verdict_groups_in_order() -> None:
    run = CitationCheck.from_dict(
        {
            "id": "r",
            "findings": [
                {"id": "1", "verdict": "not_found"},
                {"id": "2", "verdict": "verified_corpus"},
                {"id": "3", "verdict": "not_found"},
                {"id": "4"},
            ],
        }
    )
    groups = run.by_verdict()
    assert list(groups) == ["not_found", "verified_corpus", "unknown"]
    assert [f.id for f in groups["not_found"]] == ["1", "3"]


def test_to_dict_is_a_deep_copy_and_the_object_is_frozen() -> None:
    body = load("citation-checks.show.json")
    run = CitationCheck.from_dict(copy.deepcopy(body))
    dumped = run.to_dict()
    dumped["findings"].clear()
    assert run.to_dict() == body
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.id = "other"  # type: ignore[misc]


def test_open_enums_keep_values_the_sdk_does_not_know() -> None:
    run = CitationCheck.from_dict({"id": "r", "status": "brand_new", "findings": []})
    assert run.status == "brand_new"
    finding = Finding.from_dict({"id": "f", "verdict": "brand_new_verdict"})
    assert finding.verdict == "brand_new_verdict"


def test_credits_api_budget_is_a_model_and_unknown_keys_stay() -> None:
    body = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "conformance"
            / "bodies"
            / "decisions.search.api_budget.json"
        ).read_text(encoding="utf-8")
    )
    body["credits"]["api_budget"]["on_hold"] = True
    credits = DecisionSearch.from_dict(body).credits
    assert isinstance(credits.api_budget, klaracase.ApiBudget)
    assert (credits.cost, credits.credits_remaining) == (1, 0)
    assert credits.api_budget.cents == 4991
    assert credits.api_budget.rate_cents_per_credit == 9
    assert credits.api_budget.credits_at_rate == 554
    assert credits.api_budget.extra == {"on_hold": True}


def test_credits_api_budget_is_absent_not_null_when_the_key_is_missing() -> None:
    credits = DecisionSearch.from_dict(load("decisions.search.json")).credits
    assert "api_budget" not in load("decisions.search.json")["credits"]
    assert credits.api_budget is None
    assert Credits().api_budget is None
    assert DecisionSearch.from_dict({}).credits.api_budget is None
    negative = Credits.from_dict(
        {
            "metered": True,
            "cost": 1,
            "api_budget": {"cents": -40, "rate_cents_per_credit": 9, "credits_at_rate": 0},
        }
    )
    assert negative.api_budget is not None
    assert negative.api_budget.cents == -40
    assert negative.api_budget.credits_at_rate == 0
