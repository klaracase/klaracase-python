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


PRELUDE = """\
from klaracase import Klaracase

client = Klaracase()
text = ""
"""
# pydantic is not a dependency of the package, so its block is not type-checked here.
CHECKED = [block for block in BLOCKS if "pydantic" not in block]


def write_blocks(directory: Path) -> list[Path]:
    paths: list[Path] = []
    for index, block in enumerate(CHECKED):
        path = directory / f"block_{index:02d}.py"
        path.write_text(PRELUDE + block, encoding="utf-8")
        paths.append(path)
    return paths


def test_readme_python_blocks_pass_mypy_strict(tmp_path: Path) -> None:
    from mypy import api  # noqa: PLC0415

    paths = write_blocks(tmp_path)
    stdout, stderr, status = api.run(
        ["--strict", "--no-error-summary", "--cache-dir=/dev/null", *map(str, paths)]
    )
    assert status == 0, stdout + stderr


def test_readme_python_blocks_pass_pyright_strict(tmp_path: Path) -> None:
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    paths = write_blocks(tmp_path)
    (tmp_path / "pyrightconfig.json").write_text(
        '{"typeCheckingMode": "strict", "pythonVersion": "3.11"}', encoding="utf-8"
    )
    done = subprocess.run(
        [sys.executable, "-m", "pyright", "--pythonpath", sys.executable, *map(str, paths)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
