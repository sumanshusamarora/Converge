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

Stored fields:
- `hitl_questions_json` (question list)
- `hitl_resolution_json` (resolution payload)

Resolve flow:
1. task enters `HITL_REQUIRED`
2. client resolves with `POST /api/tasks/{task_id}/resolve`
3. queue transitions task back to `PENDING`
4. worker picks it up on next poll and continues run with resolution payload

## Artifact locations

By default each run writes to:

```text
.converge/runs/<timestamp>/
  summary.md
  responsibility-matrix.md
  constraints.json
  run.json
  prompts/
  repo-plans/
```

Task records store `artifacts_dir` with the run path.
