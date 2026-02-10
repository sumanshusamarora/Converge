# Copilot Instructions (Repository-wide)

## Default expectations

- Search for existing code patterns before adding new code.
- Reuse and extend existing modules; avoid unnecessary new modules.
- Keep functions small and composable.
- Add docstrings for public modules, classes, and functions.
- Add explicit type hints and keep mypy strict-clean.
- Use lazy logging style (for example: `logger.info("x=%s", x)`).
- Never log secrets, credentials, or sensitive material.

## Quality requirements

- Tests are mandatory for any behavior change.
- Run and fix these commands before finalizing:
  - `ruff check .`
  - `ruff format .`
  - `mypy`
  - `pytest`
- Keep imports ordered and remove unused imports.

## Engineering principles

- Prefer secure defaults and input validation.
- Prefer minimal dependencies.
- Use Human-in-the-Loop (HITL) for ambiguous or high-risk changes.
- Provide evidence of changes and checks in summaries.
