# CLI Reference

Converge installs one CLI entrypoint: `converge`.

## `converge coordinate`

Purpose: run one coordination workflow directly from CLI.

Usage:

```bash
converge coordinate --goal <text> --repos <path> [--repos <path> ...]
```

Key options:
- `--max-rounds` (default `2`)
- `--output-dir` (default `.converge`)
- `--model` (sets `CONVERGE_OPENAI_MODEL` for this run)
- `--coding-agent-model` (sets `CONVERGE_CODING_AGENT_MODEL` for this run; if omitted Converge auto-selects from fallback candidates)
- `--no-llm`
- `--no-tracing`
- `--hil-mode` (`conditional` or `interrupt`)
- `--coding-agent` (`codex` or `copilot`)
- `--enable-agent-exec`

Exit codes:
- `0`: run converged/succeeded
- `1`: failed/config error
- `2`: run ended `HITL_REQUIRED`

Artifacts written:
- `<output-dir>/runs/<timestamp>/summary.md`
- `<output-dir>/runs/<timestamp>/responsibility-matrix.md`
- `<output-dir>/runs/<timestamp>/constraints.json`
- `<output-dir>/runs/<timestamp>/contract-map.json`
- `<output-dir>/runs/<timestamp>/contract-checks.md`
- `<output-dir>/runs/<timestamp>/run.json`
- optional `<output-dir>/runs/<timestamp>/repo-plans/...`

Example:

```bash
converge coordinate \
  --goal "Split discount code work" \
  --repos ../api --repos ../web \
  --no-llm --hil-mode conditional
```

## `converge worker`

Purpose: poll queue and execute queued tasks.

Usage:

```bash
converge worker [--once] [--poll-interval <seconds>] [--batch-size <n>]
```

Behavior:
- claims tasks in `PENDING`
- marks each `RUNNING`
- runs orchestration
- stores result as `SUCCEEDED`, `HITL_REQUIRED`, or retry/final `FAILED`

Exit codes:
- `0`: worker command exits cleanly (`--once`)
- `1`: config/runtime error

## `converge install-codex-cli`

Purpose: print or run a shell script that installs Codex CLI.

Usage:

```bash
converge install-codex-cli [--package-manager auto|npm|pnpm|yarn] [--run]
```

Behavior:
- without `--run`: prints install script
- with `--run`: executes install script and verifies `codex --version`

## `converge doctor`

Purpose: inspect runtime readiness for Codex planning and show why Converge may fall back to heuristic planning.

Usage:

```bash
converge doctor [--json]
```

Behavior:
- reports Codex planning mode (`codex_cli` or `heuristic`)
- shows whether Codex planning will be attempted (`should_attempt_codex_plan`)
- shows Codex planning control mode (`codex_plan_mode`)
- shows resolved Codex binary path (or not found)
- shows Codex model configuration/selection and candidate fallback order
- prints fallback reasons when Codex planning path is unavailable
- prints recommendations (for example installing Codex CLI or unsetting disable flags)
- with `--json`: emits machine-readable diagnostics

## `converge server`

Purpose: run the FastAPI service for task and webhook ingestion.

Usage:

```bash
converge server [--host <host>] [--port <port>] [--reload]
```

Exit codes:
- `0`: process started / stopped cleanly
- `1`: config/runtime error
