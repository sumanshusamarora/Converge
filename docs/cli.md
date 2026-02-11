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
- `--no-llm`
- `--no-tracing`
- `--hil-mode` (`conditional` or `interrupt`)
- `--agent-provider` (`codex` or `copilot`)
- `--enable-codex-exec`

Exit codes:
- `0`: run converged/succeeded
- `1`: failed/config error
- `2`: run ended `HITL_REQUIRED`

Artifacts written:
- `<output-dir>/runs/<timestamp>/summary.md`
- `<output-dir>/runs/<timestamp>/responsibility-matrix.md`
- `<output-dir>/runs/<timestamp>/constraints.json`
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

## `converge server`

Purpose: run the FastAPI service for task and webhook ingestion.

Usage:

```bash
converge server [--host <host>] [--port <port>] [--reload]
```

Exit codes:
- `0`: process started / stopped cleanly
- `1`: config/runtime error
