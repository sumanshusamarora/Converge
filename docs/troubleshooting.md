# Troubleshooting

## Database connection errors

Symptoms:
- API or worker exits with DB config/connection errors.

Fixes:
- ensure `SQLALCHEMY_DATABASE_URI` is set when backend is `db`
- verify Postgres credentials/hostname in Docker and local shells

## Worker not picking tasks

Symptoms:
- tasks remain `PENDING`.

Fixes:
- confirm worker is running
- verify `CONVERGE_QUEUE_BACKEND=db` matches API
- check worker poll settings (`CONVERGE_WORKER_POLL_INTERVAL_SECONDS`, `CONVERGE_WORKER_BATCH_SIZE`)

## Artifacts missing

Symptoms:
- task completed but files not found in API run endpoints.

Fixes:
- verify `artifacts_dir` in task details
- ensure API `CONVERGE_OUTPUT_DIR` points to same storage root used by worker

## Tasks stuck `RUNNING`

Possible causes:
- worker crashed during run
- repeated failures before final status write

Fixes:
- restart worker
- inspect `last_error` and worker logs
- if needed, cancel and recreate task

## Missing `OPENAI_API_KEY`

Behavior:
- Converge logs info and uses heuristic proposal generation.

## Opik disabled

Behavior:
- with `OPIK_TRACK_DISABLE=true` or missing required Opik vars, Converge proceeds without tracing.

## Docker issues

- Rebuild cleanly after dependency changes:

```bash
docker-compose down -v
docker-compose up --build
```
