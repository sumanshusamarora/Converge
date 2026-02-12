# Providers and Execution

## Provider roles today

### Codex provider
- Planning is Codex-first via `codex exec` in read-only mode when CLI is available.
- Converge auto-selects a working model from fallback order (`gpt-5.3-codex -> gpt-5 -> gpt-5-mini`) unless you set `CONVERGE_CODING_AGENT_MODEL`.
- If Codex CLI planning cannot run, Converge falls back to heuristic prompt-pack generation.
- `CONVERGE_CODING_AGENT_PLAN_MODE=disable` forces heuristic planning fallback.
- `supports_execution()` returns true, but workflow integration is still plan-first and safety-gated.
- `CONVERGE_CODING_AGENT_EXEC_ENABLED=true` only enables execution gating checks; it does not turn Converge into autonomous code application by default.

### Copilot provider
- Planning-only adapter.
- Never executes code.
- Produces prompt pack style output intended for manual use in VS Code/Copilot.

## Using prompt packs in VS Code

For each repo, Converge writes:
- `repo-plans/<repo>/plan.md`
- `repo-plans/<repo>/agent-prompt.txt`
- `repo-plans/<repo>/commands.sh`

Golden path:
1. Open target repository in VS Code.
2. Open `agent-prompt.txt` from run artifacts.
3. Paste into Copilot Chat and apply iteratively.
4. Validate with repo test/lint/type checks.

## Execution modes

- `plan`: no execution expected.
- `interactive`: execution path may require TTY.
- `headless`: execution path intended for worker/container use.

Safety expectations:
- allowlisted command prefixes only
- optional clean-git enforcement
- optional auto-branch creation
