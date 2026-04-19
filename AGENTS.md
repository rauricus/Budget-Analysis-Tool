# AGENTS

## Virtual Environment for Python

- Use `uv` with a local `.venv` in this repository.
- Never create additional Python environments besides `.venv` for this project.
- Use `uv sync` to install/update dependencies from `pyproject.toml`.
- Prefer `uv run <command>` for scripts and tests.
- If activation is required in an interactive shell, use `source .venv/bin/activate`.
