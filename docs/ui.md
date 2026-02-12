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

- `/tasks`:
  - list tasks
  - filter by status
  - create a task
- `/tasks/[id]`:
  - view task details and request payload
  - view HITL questions when status is `HITL_REQUIRED`
  - cancel active tasks
  - submit HITL resolution JSON for `HITL_REQUIRED`
  - browse/download run artifacts

## Required environment variable

- `NEXT_PUBLIC_API_BASE_URL` (example: `http://localhost:8080`)
