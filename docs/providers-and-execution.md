# Providers and Execution

## Provider roles today

### Codex provider
- Planning is implemented via heuristic prompt-pack generation.
- `supports_execution()` returns true, but workflow integration is still plan-first and safety-gated.
- `CONVERGE_CODEX_ENABLED=true` only enables execution gating checks; it does not turn Converge into autonomous code application by default.

### Copilot provider
- Planning-only adapter.
- Never executes code.
- Produces prompt pack style output intended for manual use in VS Code/Copilot.

## Using prompt packs in VS Code

For each repo, Converge writes:
- `repo-plans/<repo>/plan.md`
- `repo-plans/<repo>/copilot-prompt.txt`
- `repo-plans/<repo>/commands.sh`

Golden path:
1. Open target repository in VS Code.
2. Open `copilot-prompt.txt` from run artifacts.
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
