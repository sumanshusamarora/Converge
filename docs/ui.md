# UI

Converge includes a Next.js UI under `src/frontend`.

## Run locally

```bash
cd src/frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080 npm run dev
```

Open `http://localhost:3000`.

## Pages

- `/projects`:
  - project-first home view
  - list project preferences/defaults
  - create project (name, defaults, HITL/execution preferences)
  - jump directly to project-scoped tasks
- `/tasks`:
  - project-aware task list (project filter + status filter)
  - list tasks
  - filter by project and status
  - create a task
- `/tasks/[id]`:
  - view task overview and request payload
  - timeline view for task/run lifecycle events
  - view and resolve HITL questions when status is `HITL_REQUIRED`
  - create follow-up tasks with custom instructions after plan review
  - cancel active tasks
  - submit structured HITL resolution (`answers`, `resolved_at`, optional `notes`)
  - lifecycle timing panel (queue wait, execution runtime, HITL wait, total elapsed)
  - step-duration breakdown from timeline events
  - browse/download run artifacts
  - polling refresh while task status is `CLAIMED` or `RUNNING`

## API contract used by the UI

- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/events`
- `POST /api/tasks/{task_id}/followup`
- `POST /api/tasks/{task_id}/resolve`
- `POST /api/tasks/{task_id}/cancel`
- `GET /api/projects`
- `GET /api/projects/default`
- `POST /api/projects`
- `PATCH /api/projects/{project_id}`
- `GET /api/runs/{run_id}/files`
- `GET /api/runs/{run_id}/files/{path}`

`GET /api/tasks/{task_id}/events` returns timeline events in this stable shape:

```json
{
  "id": "evt_...",
  "ts": "2026-02-13T10:20:30Z",
  "type": "TASK_CREATED",
  "title": "Task created",
  "status": "info",
  "details": {}
}
```

`GET /api/tasks` now returns a paginated envelope:

```json
{
  "items": [],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "offset": 0,
  "has_next": true,
  "has_prev": false
}
```

Query params:
- `status` (optional)
- `project_id` (optional)
- `page` (default `1`)
- `page_size` (default `20`, max `200`)

## Required environment variable

- `NEXT_PUBLIC_API_BASE_URL` (example: `http://localhost:8080`)
