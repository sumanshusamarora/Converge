# Tasks and HITL

## Task lifecycle

`PENDING -> CLAIMED -> RUNNING -> (SUCCEEDED | HITL_REQUIRED | FAILED | CANCELLED)`

Notes:
- `attempts` increments on worker failure.
- retryable failures are returned to `PENDING` until `CONVERGE_WORKER_MAX_ATTEMPTS` is reached.

## HITL behavior

HITL can be triggered when:
- repository path is missing
- proposal is ambiguous
- provider reports `HITL_REQUIRED`
- contract alignment detects cross-repository drift or unresolved contract references

Stored fields:
- `hitl_questions_json` (question list)
- `hitl_resolution_json` (resolution payload)

Resolve flow:
1. task enters `HITL_REQUIRED`
2. client resolves with `POST /api/tasks/{task_id}/resolve`
3. queue transitions task back to `PENDING`
4. worker picks it up on next poll and continues run with resolution payload

## Human input contract

Where to answer:
- UI: task details page (`/tasks/{id}`) in the **Resolve HITL Task** form
- API: `POST /api/tasks/{task_id}/resolve` with a JSON object body

What to send:
- Resolution accepts any valid JSON object.
- Recommended shape:

```json
{
  "decision": "proceed",
  "notes": "Approved with backend-first rollout"
}
```

How to know what to answer:
- Task records include `hitl_questions` for active HITL items.
- The same questions are written into run artifacts (`summary.md` and `repo-plans/*/plan.md`).

## Checkpoint/resume behavior

In `--hil-mode interrupt`, Converge can resume from a persisted LangGraph checkpoint:
- checkpoint thread id = task id
- storage backend = `SQLALCHEMY_DATABASE_URI` when set, else local SQLite `sqlite:///./converge.db`

If a DB checkpointer backend is unavailable, Converge still accepts HITL resolutions, but the next worker run starts a fresh orchestration pass (best-effort rerun).

## Artifact locations

By default each run writes to:

```text
.converge/runs/<timestamp>/
  summary.md
  responsibility-matrix.md
  constraints.json
  contract-map.json
  contract-checks.md
  run.json
  prompts/
  repo-plans/
```

Task records store `artifacts_dir` with the run path.
