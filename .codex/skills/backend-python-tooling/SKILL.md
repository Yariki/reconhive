---
name: backend-python-tooling
description: Use when configuring Python project tooling with uv, pyproject.toml, Ruff, Pyright, pytest, packaging, virtual environments, or CI commands.
---


# Python Tooling Best Practices: uv, Ruff, Pyright, pytest

## uv

- Use `pyproject.toml` as the project source of truth.
- Commit `uv.lock` for applications and services.
- Use `uv sync --locked` in CI to prevent accidental lockfile drift.
- Use `uv add` / `uv remove` instead of manually editing dependency lists when possible.
- Use dependency groups for dev/test tooling.
- Use `uv run <tool>` so commands execute inside the project environment.
- Avoid mixing Poetry, pip-tools, and uv in the same project unless migrating deliberately.

## Ruff

- Configure Ruff in `pyproject.toml`, `ruff.toml`, or `.ruff.toml`.
- Use Ruff for both formatting and linting when the repository standard allows it.
- Prefer explicit per-line ignores with a reason over broad rule suppression.
- Keep generated files excluded.
- Run format before lint in fix workflows.

Recommended command set:

```bash
uv run ruff format .
uv run ruff check . --fix
```

CI command set:

```bash
uv run ruff format --check .
uv run ruff check .
```

## Pyright

- Use strict checking for application code where practical.
- Keep public functions typed.
- Do not allow `Any` to leak across service boundaries.
- Prefer `TypedDict`, dataclasses, Pydantic models, or Protocols over unstructured dicts.
- Avoid blanket `# type: ignore`; include the exact rule and reason.

## pytest

- Keep tests isolated and deterministic.
- Prefer fixtures for setup, not hidden global state.
- Use factories/builders for data-heavy tests.
- Mark integration tests if they require database, network, filesystem, or containers.
- Test behavior, not implementation details.

## pyproject.toml Baseline

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ASYNC", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.pyright]
typeCheckingMode = "strict"
```

Adjust `target-version` to the actual supported Python version.
