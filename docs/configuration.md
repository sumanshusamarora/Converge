# Configuration

This page is the authoritative user-facing configuration list.

## Core queue + DB

| Variable | Default | When needed | Description |
|---|---|---|---|
| `SQLALCHEMY_DATABASE_URI` | _(none)_ | required when `CONVERGE_QUEUE_BACKEND=db` | SQLAlchemy database URL (SQLite/Postgres). |
| `CONVERGE_QUEUE_BACKEND` | `db` | always | Queue backend selector. `db` is implemented; `redis` and `sqs` are placeholders. |
| `CONVERGE_WORKER_POLL_INTERVAL_SECONDS` | `2` | worker | Poll interval between queue checks. |
| `CONVERGE_WORKER_BATCH_SIZE` | `1` | worker | Number of tasks claimed per poll cycle. |
| `CONVERGE_WORKER_MAX_ATTEMPTS` | `3` | worker | Max retries before final `FAILED`. |

## Output + server

| Variable | Default | When needed | Description |
|---|---|---|---|
| `CONVERGE_OUTPUT_DIR` | `.converge` | API artifact browsing | Base directory used by API `/api/runs/...` file endpoints. |
| `CONVERGE_SERVER_HOST` | `0.0.0.0` | server | Bind host for `converge server`. |
| `CONVERGE_SERVER_PORT` | `8080` | server | Bind port for `converge server`. |
| `CONVERGE_WEBHOOK_SECRET` | empty | signed webhooks | If set, webhook requests must include valid `X-Converge-Signature`. |
| `CONVERGE_WEBHOOK_MAX_BODY_BYTES` | `262144` | webhooks | Max payload size; larger payloads return `413`. |
| `CONVERGE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS` | `86400` | webhooks | Configured but currently informational only. |

## Provider + proposal behavior

| Variable | Default | When needed | Description |
|---|---|---|---|
| `CONVERGE_CODING_AGENT` | `codex` | coordinate/worker | Default coding agent if not passed in request/CLI. |
| `CONVERGE_CODING_AGENT_EXEC_ENABLED` | `false` | execution gating | Enables coding-agent execution gate checks (planning still works without execution). |
| `CONVERGE_CODING_AGENT_PATH` | `codex` | codex planning/execution | Binary/path used for coding-agent CLI invocation (Codex today). |
| `CONVERGE_CODING_AGENT_MODEL` | unset | codex planning | Force one coding-agent model for planning attempts (for example `gpt-5`). |
| `CONVERGE_CODING_AGENT_MODEL_CANDIDATES` | `gpt-5.3-codex,gpt-5,gpt-5-mini` | codex planning | Optional comma-separated fallback order used when `CONVERGE_CODING_AGENT_MODEL` is not set. |
| `CONVERGE_CODING_AGENT_PLAN_MODE` | `auto` | codex planning | Planning mode: `auto` (CLI-detected), `force` (attempt even if detection fails), `disable` (heuristic only). |
| `CONVERGE_OPENAI_MODEL` | `gpt-5-mini` | LLM proposals | Model override for proposal generation. |
| `OPENAI_API_KEY` | _(none)_ | optional | If missing, Converge falls back to heuristic proposal generation. |
| `CONVERGE_NO_LLM` | `false` | coordinate run | Force heuristic proposal path. |
| `CONVERGE_HIL_MODE` | `conditional` | coordinate run | HITL routing mode: `conditional` retry loop or `interrupt`. |

Minimal setup for Codex planning:
- install Codex CLI (`converge install-codex-cli --run`)
- set `CONVERGE_CODING_AGENT=codex`
- optionally set `CONVERGE_CODING_AGENT_MODEL=gpt-5` if your account cannot access the first auto candidate

Checkpoint resume notes:
- In `interrupt` mode, Converge attempts DB-backed LangGraph checkpoints using `SQLALCHEMY_DATABASE_URI`.
- If `SQLALCHEMY_DATABASE_URI` is not set, checkpointing defaults to local SQLite at `sqlite:///./converge.db`.
- SQLite/Postgres checkpoint backends may require additional LangGraph checkpoint packages in your runtime image.

## Execution policy settings

| Variable | Default | Description |
|---|---|---|
| `CONVERGE_EXECUTION_MODE` | `plan` | Policy mode: `plan`, `interactive`, `headless`. |
| `CONVERGE_ALLOWLISTED_CMDS` | `pytest,ruff,npm,pnpm,yarn,python,pip,git` | Allowed command prefixes for execution-capable paths. |
| `CONVERGE_REQUIRE_GIT_CLEAN` | `true` | Require clean git state before execution. |
| `CONVERGE_CREATE_BRANCH` | `true` | Create `converge/<timestamp>` branch before execution. |
| `CONVERGE_CODEX_APPLY` | `false` | Enable codex apply flow. |
| `CONVERGE_ALLOW_DIRTY` | `false` | Allow dirty git working tree in codex apply flow. |
| `CONVERGE_GIT_COMMIT` | `true` | Auto-commit in codex apply flow. |
| `CONVERGE_GIT_AUTHOR_NAME` | `Converge Bot` | Git author name for automated commits. |
| `CONVERGE_GIT_AUTHOR_EMAIL` | `converge-bot@example.com` | Git author email for automated commits. |
| `CONVERGE_MAX_CHANGED_FILES` | unset | Optional cap for changed files. |
| `CONVERGE_MAX_DIFF_LINES` | unset | Optional diff line cap. |
| `CONVERGE_MAX_DIFF_BYTES` | unset | Optional diff byte cap. |

## Observability (Opik)

| Variable | Default | Description |
|---|---|---|
| `OPIK_TRACK_DISABLE` | `false` | If truthy, disables Opik tracing immediately. |
| `OPIK_API_KEY` | _(none)_ | Required for tracing enablement. |
| `OPIK_WORKSPACE` | _(none)_ | Required for tracing enablement. |
| `OPIK_PROJECT_NAME` | _(none)_ | Required for tracing enablement. |

If required Opik vars are missing or setup fails, Converge logs warnings and continues without tracing.

## UI

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8080` | Frontend API base URL. |
