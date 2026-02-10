# AGENTS.md

Guidance for coding agents working in this repository.

## Core workflow

1. Start with repository search to find existing patterns before writing code.
2. Keep changes scoped and composable; prefer extending existing modules.
3. Add or update tests for every behavior change.
4. Run and report evidence from:
   - `ruff check .`
   - `ruff format .`
   - `mypy`
   - `pytest`

## Coding requirements

- Use Python 3.11+ and `src/` package layout.
- Add docstrings to all public modules, classes, and functions.
- Add type hints everywhere and keep mypy strict-clean.
- Use lazy logging (`logger.info("x=%s", x)`) and never log secrets.
- Keep functions small and split complex logic into helpers.

## Safety and quality

- Avoid adding dependencies unless required.
- Preserve deterministic tests.
- Prefer standard library solutions first.
- If blocked by ambiguity or security risk, request human input with options.
