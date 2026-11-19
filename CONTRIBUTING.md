# Contributing to raxtik-etl

Thank you for your interest in contributing to **raxtik-etl**!

For detailed contribution guidelines, code standards, and local documentation builds, please refer to:
👉 **[Full Contributing Guide](docs/contributing.md)**

---

## 🛠️ Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/raxtik-org/raxtik-etl.git
cd raxtik-etl

# 2. Create virtual environment with uv
uv venv --python 3.13 .venv
source .venv/bin/activate

# 3. Install in editable mode with development dependencies
uv pip install -e ".[dev,faers]"
```

---

## 🧪 Running Tests & Quality Checks

```bash
# Run test suite
uv run pytest tests/ -v

# Run linter and formatter
uv run ruff check .
uv run ruff format .
```
