"""Check a built wheel: it must ship ``py.typed`` and the package, and must not ship tests.

Usage:  uv build && uv run python scripts/check_wheel.py dist/klaracase-*.whl
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REQUIRED = (
    "klaracase/__init__.py",
    "klaracase/py.typed",
    "klaracase/agents.py",
    "klaracase/types.py",
    "klaracase/errors.py",
)


def problems(wheel: Path) -> list[str]:
    """Return what is wrong with the wheel, or an empty list."""
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        found = [f"missing {name}" for name in REQUIRED if name not in names]
        found += [f"unexpected {name}" for name in sorted(names) if name.startswith("tests/")]
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if not metadata:
            found.append("missing METADATA")
        else:
            text = archive.read(metadata[0]).decode("utf-8")
            if "Requires-Dist: httpx2" not in text:
                found.append("METADATA does not require httpx2")
            if "Classifier: Typing :: Typed" not in text:
                found.append("METADATA lacks the Typing :: Typed classifier")
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_wheel.py WHEEL...")
        return 2
    failed = False
    for argument in argv:
        issues = problems(Path(argument))
        for issue in issues:
            print(f"{argument}: {issue}")
        failed = failed or bool(issues)
        if not issues:
            print(f"{argument}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
