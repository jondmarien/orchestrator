SHELL := pwsh

.PHONY: help install pre-commit format lint test check clean

help:
	@echo "Common tasks:"
	@echo "  make install        - Install dev tools (pre-commit hooks)"
	@echo "  make pre-commit     - Run pre-commit on all files"
	@echo "  make format         - Run ruff format and import sort"
	@echo "  make lint           - Run ruff lint"
	@echo "  make test           - Run pytest"
	@echo "  make check          - Format+lint+test"
	@echo "  make clean          - Remove caches and build artifacts"

install:
	uv sync
	uv tool install pre-commit || uv pip install pre-commit
	pre-commit install

pre-commit:
	pre-commit run --all-files

format:
	uv run ruff format
	uv run ruff check --select I --fix

lint:
	uv run ruff check

test:
	uv run pytest

check: format lint test

clean:
	powershell -NoProfile -Command "Get-ChildItem -Recurse -Force -ErrorAction SilentlyContinue -Include __pycache__,.pytest_cache,.ruff_cache,htmlcov,*.egg-info | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
