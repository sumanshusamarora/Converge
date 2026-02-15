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

## Codex model access errors

Symptoms:
- Logs include messages like `model ... does not exist or you do not have access`
- Codex planning repeatedly retries, then falls back

Fixes:
- run `converge doctor` and inspect `codex_model_candidates`
- set `CONVERGE_CODING_AGENT_MODEL` to a model your account can access (for example `gpt-5`)
- or tune fallback order via `CONVERGE_CODING_AGENT_MODEL_CANDIDATES`

## Opik disabled

Behavior:
- with `OPIK_TRACK_DISABLE=true` or missing required Opik vars, Converge proceeds without tracing.

## Docker issues

- Rebuild cleanly after dependency changes:

```bash
docker compose down -v
docker compose up --build
```

- If startup fails with `address already in use`, set host port overrides in `.env`:
  - `CONVERGE_API_HOST_PORT` (default `8080`)
  - `CONVERGE_FRONTEND_HOST_PORT` (default `3000`)

- Postgres is internal-only in default compose setup. If you need host DB access, add a port mapping for `postgres` in a local compose override file.

## Frontend `Cannot find module './411.js'` (or similar chunk id)

Symptoms:
- Next.js dev server returns `500` on `/tasks` (or other pages)
- Logs include errors like:
  - `Cannot find module './411.js'`
  - `Require stack: ... .next/server/webpack-runtime.js`

Cause:
- Stale/corrupted `.next` artifacts, often after switching between `next build/start` and `next dev`.
- Mixed dev/prod chunk outputs in the same build folder can also trigger this class of runtime module errors.

Fix:

```bash
cd src/frontend
npm run clean
npm run dev
```

Note:
- Converge frontend now writes dev output to `.next-dev` and production output to `.next` to reduce cross-mode cache conflicts.

If it still fails, fully refresh dependencies:

```bash
cd src/frontend
rm -rf node_modules package-lock.json .next
npm install
npm run dev
```
