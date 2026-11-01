"""Copy lint: banned wording must not appear in the README, CHANGELOG, manifest or source."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

FORBIDDEN = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"hallucinat",
        r"halluzin",
        r"fabricat",
        r"fabrizier",
        r"\bfake\b",
        r"official source",
        r"offizielle quelle",
        r"amtlich",
    )
]

# The required disclaimer says "fabricated" once. Only this exact sentence is exempt.
ALLOWED_SENTENCE = re.compile(r"it is not a claim that the citation is fabricated\.", re.IGNORECASE)


def find_forbidden(text: str) -> list[str]:
    cleaned = ALLOWED_SENTENCE.sub("", " ".join(text.split()))
    return [pattern.pattern for pattern in FORBIDDEN if pattern.search(cleaned)]


def scanned_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "pyproject.toml"]
    files += sorted((ROOT / "src").rglob("*.py"))
    return files


def test_no_forbidden_wording_in_docs_manifest_and_source() -> None:
    hits = [
        f"{path.relative_to(ROOT)}: {pattern}"
        for path in scanned_files()
        for pattern in find_forbidden(path.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_every_forbidden_pattern_is_flagged() -> None:
    samples = [
        "This stops hallucinations.",
        "Das verhindert Halluzinationen.",
        "The citation is Fabricated.",
        "Das ist fabriziert.",
        "A fake case.",
        "The official source of law.",
        "Die offizielle Quelle.",
        "Der amtliche Leitsatz.",
    ]
    for sample in samples:
        assert find_forbidden(sample) != [], sample


def test_the_required_disclaimer_is_allowed_and_nothing_around_it() -> None:
    sentence = (
        "A `not_found` verdict means the citation was not found in the corpus; it is not a\n"
        "claim that the citation is fabricated."
    )
    assert find_forbidden(sentence) == []
    assert find_forbidden(sentence + " It is fabricated.") != []
    assert find_forbidden("A fake.") != []
