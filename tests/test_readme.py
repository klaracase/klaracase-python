"""The README code blocks must at least be valid Python, and must not hold a real token."""

from __future__ import annotations

import ast
import re
from pathlib import Path

README = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
BLOCKS = re.findall(r"```python\n(.*?)```", README, flags=re.DOTALL)


def test_readme_has_python_blocks() -> None:
    assert len(BLOCKS) >= 8


def test_readme_python_blocks_parse() -> None:
    for block in BLOCKS:
        compile(block, "README.md", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, dont_inherit=True)


def test_readme_states_the_required_sentences() -> None:
    flat = " ".join(README.split())
    assert "Klaracase covers German law only." in flat
    assert "It is a research tool." in flat
    assert "It gives no legal advice and does not replace a lawyer's review." in flat
    assert (
        "A `not_found` verdict means the citation was not found in the corpus; it is not a claim "
        "that the citation is fabricated." in flat
    )


def test_readme_has_no_em_dash_and_only_placeholder_tokens() -> None:
    assert "—" not in README
    assert not re.search(r"klc_(?!your_token_here)\w{8,}", README)
