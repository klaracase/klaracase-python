"""Check the citations in a text and read the findings. Runs against a local mock.

    uv run python examples/citation_check.py

The mock replays a canned answer, so the sample text below is built to match its offsets. With
the real API the offsets always match the exact text you send.
"""

from __future__ import annotations

from _mock_api import mock_client

CITATION = "BGH, Urt. v. 15.11.2001 \u2013 1 StR 185/01"
TEXT = "Der Geschäftsführer verletzte seine Vermögensbetreuungspflicht, vgl. ".ljust(118, ".")
TEXT += CITATION + ". Dort ist die Rechtsprechung des Bundesgerichtshofs zusammengefasst."


def main() -> None:
    with mock_client() as client:
        run = client.citation_checks.create(text=TEXT, reference_date="2026-10-01")
        if run.status != "complete":
            print("The run did not finish:", run.status)
            return
        print("run", run.id, "| verdicts:", run.verdict_counts, "| cost:", run.credits.cost)

        for verdict, findings in run.by_verdict().items():
            for finding in findings:
                print(f"{verdict:<16} {finding.canonical}  <- {finding.excerpt(TEXT)!r}")
                if verdict == "not_found":
                    print("  Not found in the corpus. Check it by hand.")


if __name__ == "__main__":
    main()
