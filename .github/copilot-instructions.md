# Copilot Instructions (Repository-wide)

You are an AI coding agent working on this repository. Follow these rules strictly.

## Non-negotiables
- Prefer correctness, security, scalability, and maintainability over cleverness.
- Never assume; verify by reading existing code and running checks.
- Keep changes minimal and well-scoped. Avoid broad refactors unless requested or required.
- If requirements are ambiguous or risky, raise a Human-in-the-Loop (HITL) question with clear options and tradeoffs.

## Before writing code
1. Search the codebase for existing patterns, utilities, and conventions. Reuse them.
2. Identify the correct module to extend (avoid new modules if an existing one fits).
3. Confirm the expected behavior by locating:
   - Existing tests
   - Similar endpoints/components
   - Existing schemas/contracts
4. Write down a short plan (3–6 bullets) before making edits when work is non-trivial.

## Implementation guidelines
- Prefer small, composable functions. Break complex methods into smaller helpers.
- Keep functions/classes single-purpose.
- Use clear names; avoid abbreviations unless already established in the repo.
- Add docstrings for public functions/classes and any non-obvious logic.
- Add type hints (Python) and strong typing (TS) wherever feasible.
- Logging:
  - Use lazy logging style (e.g., logger.info("x=%s", x)) to avoid eager formatting.
  - Never log secrets, tokens, credentials, or sensitive customer data.

## Tests are mandatory
- Add or update tests for every behavior change (happy path + key edge cases).
- If you fix a bug, add a regression test that fails before the fix.
- Always run the relevant test suite(s) locally before concluding.
- If tests are slow, run the smallest targeted subset first, then the full suite when practical.

## Quality gates (Python)
- Format with **black**.
- Lint with **ruff** (including unused imports, import order, and common correctness checks).
- Ensure there are **no unused imports** and imports are correctly ordered.
- Prefer ruff fixes when safe; do not hide real issues with ignores.
- Keep cyclomatic complexity reasonable; refactor large functions.

## Quality gates (TypeScript/Frontend)
- Run typecheck and lint before finalizing changes.
- Avoid `any` unless unavoidable; prefer strict types and discriminated unions where helpful.
- Keep UI changes accessible (keyboard nav, aria labels where needed).
- Prefer existing components, styling patterns, and state management conventions.

## API contracts & cross-module boundaries
- Treat the API contract as a first-class artifact:
  - Keep request/response shapes consistent and version-safe.
  - Prefer backwards-compatible changes (additive fields, optional properties).
- Validate contract changes with:
  - Backend schema validation / OpenAPI updates (if present)
  - Frontend client generation or type validation (if present)
- Clearly document any breaking changes and provide migration notes.
- Decide “where logic lives” by:
  - Backend owns validation, authorization, persistence, and business rules.
  - Frontend owns presentation, UX state, and client-side input constraints (not security).
  - Avoid duplicating business logic across layers.

## Security & safety
- Never introduce insecure defaults:
  - Validate inputs
  - Use safe parameterized queries
  - Apply authz checks server-side
  - Avoid SSRF/command injection patterns
- Do not add dependencies without strong justification. Prefer standard library / existing deps.
- If your change touches auth, payments, PII, encryption, or infra, escalate to HITL.

## Performance & scalability
- Avoid N+1 patterns (DB and network).
- Batch where appropriate; paginate large collections.
- Prefer async/background processing for long-running tasks where the repo already supports it.
- Add basic instrumentation/logs for new critical paths (but keep logs non-sensitive).

## Documentation & developer experience
- Update README / docs when behavior or setup changes.
- Add comments only where needed to explain “why”, not “what”.
- Keep config consistent with the repo conventions.

## Always run these before finishing (adapt to repo)
- Python:
  - `ruff check .`
  - `black .`
  - `pytest` (or repo test runner)
- Frontend:
  - `npm/yarn/pnpm lint`
  - `npm/yarn/pnpm typecheck`
  - `npm/yarn/pnpm test` (or repo test runner)
If you cannot run a command, explain why and propose the next best verification.

## Output expectations
- Provide a short summary of changes.
- Provide evidence: commands run + results, and what tests were added/updated.
- If tradeoffs exist, list them and recommend one option.
- If blocked or risky, raise HITL with a concise question and 2–3 options.

## Project Intent: Cross-Repo Coordination

- This repository is not a single application.
- It is an orchestration and governance tool.
- Code changes in external repos may be proposed, not automatically applied.
- Always think in terms of:
  - responsibility boundaries
  - contracts between repos
  - safest place for logic to live
- Prefer generating summaries, plans, and evidence
  before suggesting implementation.
