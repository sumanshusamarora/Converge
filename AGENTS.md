# Codex Agent Instructions

You are a Codex agent working on the Converge repository. These instructions govern safe execution, bounded loops, and collaboration.

## Core Principles

1. **Safety First**: Never execute commands that could:
   - Leak secrets, tokens, or credentials
   - Modify code outside the designated repository
   - Bypass security controls or execute arbitrary code without validation
   - Cause data loss or irreversible changes without explicit permission

2. **Bounded Convergence**: 
   - Default max rounds: 2
   - Stop and raise HITL when:
     - Requirements are ambiguous
     - Risks involve security, breaking changes, or unclear ownership
     - Unable to make progress after max attempts
   - Use new information from each iteration to converge on a solution

3. **Git Hygiene**:
   - Always verify `.git` directory exists before operations
   - Default behavior: create new branch with prefix `converge/`
   - Alternative: require clean working directory (no uncommitted changes)
   - Never force-push or rewrite history
   - Always stage, commit, and push changes with descriptive messages

## Execution Policy

Codex execution is gated by **ALL** of the following:

1. **Environment**: `CONVERGE_CODING_AGENT_EXEC_ENABLED=true` must be set
2. **Task flag**: Explicit `--allow-exec` or equivalent flag in task/CLI
3. **Repository safety checks**:
   - Repository exists and has `.git` directory
   - If `require_git_clean=true`: working directory must be clean
   - If `create_branch=true`: create and checkout new branch `converge/<timestamp>`

## Command Allowlist

Only the following command prefixes are allowed during execution:
- `pytest` - Run tests
- `ruff` - Linting and formatting
- `black` - Code formatting  
- `mypy` - Type checking
- `npm`, `pnpm`, `yarn` - JavaScript package management and scripts
- `python` - Run Python scripts/modules
- `pip` - Python package installation
- `git` - Git operations (with safety checks)
- `cat`, `ls`, `find`, `grep` - Read-only file operations
- `mkdir`, `touch` - Safe file creation

Commands are matched by **prefix**. Any command not in the allowlist is rejected.

## Before Writing Code

1. Read existing code to understand patterns and conventions
2. Identify the minimal set of files to modify
3. Verify behavior by locating:
   - Existing tests
   - Similar implementations
   - API contracts/schemas
4. Write a short plan (3-6 bullets) before making changes

## Implementation Guidelines

- **Minimal changes**: Change as few lines as possible
- **Type safety**: Add type hints to all new functions
- **Testing**: Add or update tests for all behavior changes
- **Logging**: Use lazy logging style: `logger.info("x=%s", x)`
- **No secrets**: Never log or commit secrets, tokens, or credentials
- **Documentation**: Update docs only if interfaces change

## Quality Gates

Before finalizing changes, run:
```bash
ruff check .
ruff format .
mypy src/
pytest
```

All checks must pass. If mypy has `ignore_errors` for orchestration modules, fix those type issues.

## Security & Secrets

- **Never** hardcode or print secrets
- `.env` is local-only; `.env.example` contains placeholders only
- Validate all inputs before execution
- Use parameterized queries, never string concatenation
- Apply authorization checks server-side
- If change touches auth, encryption, or PII: STOP and raise HITL

## Collaboration with Copilot

- Copilot is **planning-only** and never executes code
- Codex may execute when conditions are met (see Execution Policy)
- Both agents coordinate through Converge's orchestration layer
- Respect ownership boundaries between repositories

## When to Stop and Raise HITL

Stop immediately and request human judgment when:
- Requirements are unclear or conflicting
- Multiple valid approaches exist with different tradeoffs
- Change involves security, breaking API changes, or architectural decisions
- Unable to make progress after max attempts
- Repository structure is unclear or signals are missing
- Tests fail and root cause is unclear

## Error Handling

- Treat all external operations as fallible
- Log errors with context but without sensitive data
- Fail fast and clearly communicate what went wrong
- Provide actionable next steps or questions for HITL

## Documentation Sync Requirement

Any change that affects user-facing behavior (CLI flags/commands, environment variables, artifact layout, API endpoints, or UI behavior) **must** include matching updates in `docs/` in the same change set.

`docs/` is user-facing only: do not place internal implementation notes or iteration logs there.
