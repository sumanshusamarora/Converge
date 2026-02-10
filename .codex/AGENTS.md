# Codex Agent Instructions

**This file provides Codex-specific execution guidance.**

For complete instructions, see the root-level [AGENTS.md](../AGENTS.md).

## Codex-Specific Notes

This directory (`.codex/`) may contain Codex CLI configurations and workspace-specific overrides.
The primary instruction set is maintained in the repository root for consistency.

When using Codex CLI:
- Execution requires `CONVERGE_CODEX_ENABLED=true` environment variable
- Commands must be on the allowlist (see root AGENTS.md)
- Repository safety checks are enforced (git clean or new branch)
- All changes must pass quality gates: ruff, mypy, pytest
