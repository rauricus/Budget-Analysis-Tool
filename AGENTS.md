# AGENTS

## Python Environment

- Never create a new virtual environment in this repository.
- Always use the existing Micromamba environment named `bat`.
- Prefer `micromamba run -n bat <command>` for scripts and tests.
- If `-n bat` does not resolve due prefix differences, use the explicit environment path with `micromamba run -p /Users/andreas/micromamba/envs/bat <command>`.
- If activation is required in an interactive shell, use `micromamba activate bat`.
