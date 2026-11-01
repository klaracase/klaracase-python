"""Smoke test against the real API. Calls the free endpoints only. Not part of CI.

Usage:  KLARACASE_API_TOKEN=<token> uv run python scripts/smoke.py
"""

from __future__ import annotations

import sys

import klaracase


def main() -> int:
    try:
        client = klaracase.Klaracase()
    except klaracase.ConfigurationError as exc:
        print(exc)
        return 2
    with client:
        coverage = client.corpus.coverage(top=3)
        total = coverage.total_decisions.value if coverage.total_decisions else None
        print(
            f"coverage ok: status={coverage.meta.status} api_release={coverage.meta.api_release} "
            f"decisions={total} duration={coverage.meta.request_duration:.2f}s"
        )
        facets = client.corpus.facets("court_name", prefix="BGH")
        print(f"facets ok: {facets.field} total_values={facets.total_values}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
