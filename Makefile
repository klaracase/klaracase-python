.PHONY: sync test lint format typecheck smoke build

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

# Calls the free endpoints only. Needs a real token: KLARACASE_API_TOKEN. Not part of CI.
smoke:
	uv run python scripts/smoke.py

build:
	uv build
