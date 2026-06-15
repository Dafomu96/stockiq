# Contributing to StockIQ

## Commit conventions (Conventional Commits)

Every commit message must follow this format:

```
<type>(<scope>): <short description in English, imperative mood>

[optional body — explain WHY, not what]

[optional footer — Breaking changes, closes #issue]
```

### Types

| Type | When to use |
|---|---|
| `feat` | New feature or behaviour |
| `fix` | Bug fix |
| `test` | Adding or updating tests |
| `refactor` | Code change without new feature or fix |
| `docs` | Documentation only |
| `chore` | Build, CI, dependencies, tooling |
| `perf` | Performance improvement |

### Examples

```
feat(scoring): add FundamentalOnlyStrategy for dividend-free stocks

fix(fetcher): handle missing dividend fields in yfinance .info

test(api): add smoke test for /v1/analyze with mocked fetcher

chore(ci): add Docker build job to CI pipeline

docs(adr): add ADR-005 — Docker and CI strategy
```

---

## Branch strategy

- `main` — protected. All changes via PR. Direct pushes blocked by pre-commit.
- `feat/<name>` — new features (e.g. `feat/react-frontend`)
- `fix/<name>` — bug fixes (e.g. `fix/gordon-zero-dividend`)
- `chore/<name>` — tooling, CI, dependencies

---

## Development setup

```bash
git clone https://github.com/Dafomu96/stockiq.git
cd stockiq
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pre-commit install           # install git hooks
pytest tests/ --asyncio-mode=auto   # all tests must pass
```

---

## Running locally

```bash
# Streamlit MVP
streamlit run app/streamlit_app.py

# FastAPI backend
uvicorn backend.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs

# Both via Docker Compose
docker compose up
```

---

## Before opening a PR

- [ ] `pytest tests/ --asyncio-mode=auto` — all pass, coverage ≥85%
- [ ] `ruff check .` — no lint errors
- [ ] `black --check .` — no format issues
- [ ] `mypy config/ data/ analysis/ simulation/ backend/ --ignore-missing-imports` — no type errors
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] ADR added if a significant architectural decision was made
