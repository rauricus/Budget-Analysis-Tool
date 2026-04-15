# AGENTS

## Virtual Environment for Python

- Use the existing Micromamba environment named `bat`. Never create a new (Python) virtual environment in this repository.
- Prefer `micromamba run -n bat <command>` for scripts and tests.
- If `-n bat` does not resolve due prefix differences, use the explicit environment path with `micromamba run -p /Users/andreas/micromamba/envs/bat <command>`.
- If activation is required in an interactive shell, use `micromamba activate bat`.
