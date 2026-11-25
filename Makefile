.PHONY: install test lint typecheck quality format docs clean

install:
	uv sync --all-extras --dev

test:
	uv run pytest -v --cov=raxtik_etl tests/

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

typecheck:
	uv run pyrefly check src/

quality: lint typecheck

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

docs:
	uvx --with tox-uv tox run -e docs

clean:
	rm -rf .pytest_cache htmlcov .coverage coverage.xml dist build *.egg-info .ruff_cache docs/_build .tox
