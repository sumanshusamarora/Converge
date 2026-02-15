# Codex CLI for Converge (Internal)

Last validated: 2026-02-13
Codex CLI version: `0.92.0`

## Purpose

This document summarizes Codex CLI commands and input patterns from Converge's usage perspective:
- non-interactive planning (`codex exec`)
- model selection and fallback behavior
- machine-readable outputs (`--json`, `--output-last-message`, `--output-schema`)
- authentication and troubleshooting

## Top-Level Commands

From `codex --help`:
- `exec`
- `review`
- `login`
- `logout`
- `mcp`
- `mcp-server`
- `app-server`
- `completion`
- `sandbox`
- `apply`
- `resume`
- `fork`
- `cloud`
- `features`

## Subcommands Discovered

### `exec`
- `exec resume`
- `exec review`

### `login`
- `login status`

### `mcp`
- `mcp list`
- `mcp get`
- `mcp add`
- `mcp remove`
- `mcp login`
- `mcp logout`

### `app-server`
- `app-server generate-ts`
- `app-server generate-json-schema`

### `cloud`
- `cloud exec`
- `cloud status`
- `cloud list`
- `cloud apply`
- `cloud diff`

### `features`
- `features list`

### `sandbox`
- `sandbox linux`
- `sandbox macos`
- `sandbox windows`

## Inputs for `codex exec` (Converge-critical)

`codex exec` accepts:
- Prompt as positional argument
- Prompt from stdin when positional prompt is omitted or `-` is used
- Model via `-m, --model`
- Working directory via `-C, --cd`
- Sandbox mode via `-s, --sandbox` (`read-only`, `workspace-write`, `danger-full-access`)
- Approval policy via `-a, --ask-for-approval`
- JSON schema contract via `--output-schema <FILE>`
- Final assistant message sink via `--output-last-message <FILE>`
- Event stream output via `--json` (JSONL)
- Image inputs via `-i, --image`
- Additional writable dirs via `--add-dir`

Converge planning path uses:
- `codex -a never exec`
- `--sandbox read-only`
- `--skip-git-repo-check`
- `--output-schema ...`
- `--output-last-message ...`
- `-C <repo>`
- `-m <model>`

## Authentication Inputs

`codex login` supports:
- interactive/device login
- `--with-api-key` (read key from stdin)

`codex login status` reports current auth state.

Observed in this environment:
- `codex login status` => `Logged in using ChatGPT`

## Real Model Probes (Non-interactive)

### Probe A: schema-constrained exec
Command shape:
- `codex -a never exec -m <model> --sandbox read-only --skip-git-repo-check --output-schema schema.json --output-last-message out.json -C <repo> "Return JSON only ..."`

Observed results:
- `-m gpt-5.3-codex` => exit `1`, empty output file, repeated retry logs, final error:
  - `The model gpt-5.3-codex does not exist or you do not have access to it.`
- `-m gpt-5` => exit `0`, output file contains valid JSON payload.

### Probe B: JSONL event stream
Command shape:
- `codex -a never exec -m gpt-5 --sandbox read-only --skip-git-repo-check --json -C <repo> "Reply with exactly: ok"`

Observed output types:
- `thread.started`
- `turn.started`
- `item.completed` (reasoning, agent_message)
- `turn.completed` (token usage)

## Additional Runtime Probes

### `codex features list`

Observed behavior:
- Returns a table of feature flags with stage and effective enabled state.
- Useful for debugging environment-specific behavior changes.

### `codex mcp list`

Observed behavior:
- When no servers are configured, returns:
  - `No MCP servers configured yet. Try 'codex mcp add my-tool -- my-command'.`

### `codex cloud list --limit 3`

Observed behavior:
- Successfully returned recent cloud tasks with status, title, repo, and diff stats.
- Supports pagination via `--cursor`.

## Command Templates for Converge Operators

### 1) Health check
```bash
codex --version
codex login status
```

### 2) Minimal non-interactive planning probe
```bash
codex -a never exec \
  -m gpt-5 \
  --sandbox read-only \
  --skip-git-repo-check \
  -C /path/to/repo \
  "Reply with exactly: ok"
```

### 3) Schema-constrained output probe
```bash
codex -a never exec \
  -m gpt-5 \
  --sandbox read-only \
  --skip-git-repo-check \
  --output-schema /tmp/schema.json \
  --output-last-message /tmp/out.json \
  -C /path/to/repo \
  "Return JSON only: {\"summary\":\"ok\"}"
```

### 4) JSONL integration probe
```bash
codex -a never exec \
  -m gpt-5 \
  --sandbox read-only \
  --skip-git-repo-check \
  --json \
  -C /path/to/repo \
  "Reply with exactly: ok"
```

## Recommended Converge Settings

For current observed behavior:
- `CONVERGE_CODING_AGENT=codex`
- `CONVERGE_CODING_AGENT_MODEL=gpt-5`
- `CONVERGE_CODING_AGENT_PLAN_MODE=auto`
- `CONVERGE_CODING_AGENT_PATH=codex`

Optional fallback list if model availability changes:
- `CONVERGE_CODING_AGENT_MODEL_CANDIDATES="gpt-5.3-codex,gpt-5,gpt-5-mini"`

## Troubleshooting Notes

1. Session path permission failures
- Symptom: `Codex cannot access session files at ~/.codex/sessions`.
- Cause: file ownership/permission mismatch or sandbox restrictions.
- Fix: ensure correct ownership/permissions for `~/.codex`.

2. Model access errors
- Symptom: retries then `does not exist or you do not have access`.
- Action: test explicit model with `codex exec -m <model> ...` and set `CONVERGE_CODING_AGENT_MODEL` to a known-good value.

3. Helpful diagnostics in Converge
- `converge doctor` shows planning mode, model candidates, selected model, and fallback reasons.
