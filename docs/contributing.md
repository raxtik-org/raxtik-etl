# Contributing to raxtik-etl

Thank you for your interest in contributing to **raxtik-etl**! We welcome bug reports, feature suggestions, documentation improvements, and code contributions.

---

## 🛠️ Development Setup

The project uses modular requirement files matching the Watchdog architecture:
* `requirements-lint.txt` - Code style, spelling, and static typing (Ruff, Typos, Pyrefly)
* `requirements-docs.txt` - Sphinx documentation and Read the Docs dependencies
* `requirements-tests.txt` - Automated testing and test coverage
* `requirements-dev.txt` - All development dependencies combined

```bash
# Clone the repository
git clone https://github.com/raxtik-org/raxtik-etl.git
cd raxtik-etl

# Create virtualenv and install full development suite
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e . -r requirements-dev.txt

# Or install only test dependencies:
uv pip install -e . -r requirements-tests.txt
```

---

## 🧪 Testing

Run the full automated test suite with `pytest`:

```bash
pytest tests/ -v
```

Or run via `tox`:
```bash
tox -e py313
```

---

## 🧹 Code Quality & Formatting

We use **Ruff** for linting and formatting, **Typos** for spell checking, and **Pre-commit** for automation.

### PR Auto-Formatting (Zero Hassle)

You do **not** need to install or run local pre-commit git hooks.

When you open a Pull Request:
1. `pre-commit.ci` automatically runs Ruff formatting, import sorting, and Typos checks.
2. Any formatting or lint fixes are automatically committed directly to your PR branch.

### Manual Local Checks (Optional)

If you wish to check or format code locally before pushing:

```bash
# Lint and format with Ruff
uv run ruff check --fix .
uv run ruff format .

# Check for spelling errors with Typos
uv run --with typos typos

# Run pre-commit hooks manually across all files
uv run --with pre-commit pre-commit run --all-files
```

---

## 🔍 Type Hint Checking
 
We enforce strict static type annotations. We use **Pyrefly** (Meta's Rust-powered type checker) for sub-second verification in both local development and CI:

```bash
uv run pyrefly check src/raxtik_etl
```

---

## 📚 Building Documentation

Documentation is built with Sphinx and MyST Markdown parser:

```bash
# Build HTML documentation locally
uv run sphinx-build -b html docs docs/_build/html -W
```

---

## 🤖 All Contributors Bot

We value all contributions! To recognize a contributor, comment on any Pull Request or Issue with:

```text
@all-contributors please add @<username> for <contributions>
```

Common contribution keys:
- `code` - Code improvements or bug fixes
- `doc` - Documentation updates or corrections
- `test` - Adding or fixing tests
- `bug` - Reporting or identifying bugs
- `review` - Reviewing pull requests
- `ideas` - Discussing architecture and features
