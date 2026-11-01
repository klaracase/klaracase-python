"""Search, read a decision, read a norm and look at the corpus. Runs against a local mock.

    uv run python examples/quickstart.py

Swap ``mock_client()`` for ``Klaracase()`` (token in KLARACASE_API_TOKEN) to use the real API.
"""

from __future__ import annotations

from _mock_api import mock_client
from klaracase import KlaracaseError


def main() -> None:
    with mock_client() as client:
        result = client.decisions.search("Vermögensbetreuungspflicht Geschäftsführer", court="BGH")
        for hit in result.results:
            print(hit.aktenzeichen, hit.court, hit.date, hit.title)
        print("credits:", result.credits.cost, "left:", result.credits.credits_remaining)

        decision = client.decisions.get(result.results[0].id, section="Leitsatz")
        print("ECLI:", decision.ecli, "| type:", decision.document_type)

        norm = client.norms.get("§ 535 BGB")
        if norm.norm is not None:
            print(norm.reference, "-", norm.norm.title)

        coverage = client.corpus.coverage(top=5)
        if coverage.total_decisions is not None:
            print("decisions in the corpus:", coverage.total_decisions.value)

        try:
            client.decisions.get("VIII ZR 999/99")
        except KlaracaseError as error:
            print("error:", error.status_code, error.code, "retryable:", error.retryable)


if __name__ == "__main__":
    main()
