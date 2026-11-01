.PHONY: sync test lint format typecheck smoke build wheel-check

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy
	uv run pyright

# Calls the free endpoints only. Needs a real token: KLARACASE_API_TOKEN. Not part of CI.
smoke:
	uv run python scripts/smoke.py

build:
	uv build

# Builds the wheel and checks that py.typed and the package ship.
wheel-check: build
	uv run python scripts/check_wheel.py dist/*.whl
