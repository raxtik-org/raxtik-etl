.PHONY: install test lint format sample-run clean

install:
	uv pip install -e ".[dev]"

test:
	pytest -v --cov=raxtik_etl tests/

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

sample-run:
	raxtik-etl pipeline --sample --output-dir data/output

docs:
	tox run -e docs

clean:
	rm -rf .pytest_cache htmlcov .coverage dist build *.egg-info .ruff_cache docs/_build .tox
