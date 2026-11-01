"""The built package, the examples and the lazy async import."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_wheel  # noqa: E402  (scripts/ is not a package)


def make_wheel(path: Path, names: list[str], requires: str = "Requires-Dist: httpx2>=2.12") -> Path:
    wheel = path / "klaracase-0.1.0-py3-none-any.whl"
    metadata = f"Metadata-Version: 2.5\nName: klaracase\n{requires}\nClassifier: Typing :: Typed\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in names:
            archive.writestr(name, "")
        archive.writestr("klaracase-0.1.0.dist-info/METADATA", metadata)
    return wheel


GOOD = list(check_wheel.REQUIRED)


def test_the_wheel_check_accepts_a_good_wheel(tmp_path: Path) -> None:
    assert check_wheel.problems(make_wheel(tmp_path, GOOD)) == []


def test_the_wheel_check_fails_without_py_typed(tmp_path: Path) -> None:
    names = [name for name in GOOD if name != "klaracase/py.typed"]
    assert check_wheel.problems(make_wheel(tmp_path, names)) == ["missing klaracase/py.typed"]


def test_the_wheel_check_fails_on_tests_and_a_wrong_dependency(tmp_path: Path) -> None:
    wheel = make_wheel(tmp_path, [*GOOD, "tests/test_x.py"], requires="Requires-Dist: httpx>=0.27")
    assert check_wheel.problems(wheel) == [
        "unexpected tests/test_x.py",
        "METADATA does not require httpx2",
    ]


def test_importing_the_package_does_not_import_the_async_client() -> None:
    code = (
        "import sys, klaracase;"
        "assert 'klaracase._async' not in sys.modules;"
        "client_class = klaracase.AsyncKlaracase;"
        "assert 'klaracase._async' in sys.modules;"
        "assert client_class.__module__ == 'klaracase';"
        "from klaracase import AsyncKlaracase; assert AsyncKlaracase is client_class;"
        "import klaracase.agents; print('ok')"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("quickstart.py", ["1 StR 185/01 BGH", "error: 404 not_found retryable: False"]),
        ("citation_check.py", ["verified_corpus", "<- 'BGH, Urt. v. 15.11.2001"]),
        ("agent_loop.py", ["tools: search_decisions", "error unknown_tool"]),
    ],
)
def test_the_examples_run_against_the_local_mock(
    script: str, expected: list[str], tmp_path: Path
) -> None:
    done = subprocess.run(
        [sys.executable, str(ROOT / "examples" / script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "", "KLARACASE_API_TOKEN": ""},
    )
    assert done.returncode == 0, done.stderr
    for text in expected:
        assert text in done.stdout, done.stdout
