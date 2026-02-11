# Getting Started

## Prerequisites

- Python 3.10+
- Node.js 18+ (for UI)
- Docker + Docker Compose (for containerized setup)

## Install (local)

```bash
pip install -e ".[dev]"
pip install -e ".[docs]"
```

## Quickstart 1: Local (SQLite)

```bash
export SQLALCHEMY_DATABASE_URI="sqlite:///./converge.db"
export CONVERGE_QUEUE_BACKEND="db"
export OPIK_TRACK_DISABLE="true"

# Terminal 1
converge server --port 8080

# Terminal 2
converge worker

# Terminal 3 (optional UI)
cd src/frontend
npm install
npm run dev
```

Create a task with API:

```bash
python - <<'PY'
import requests
payload={"goal":"Document rollout behavior","repos":["/workspace/Converge"],"max_rounds":2}
print(requests.post("http://localhost:8080/api/tasks", json=payload, timeout=10).json())
PY
```

Expected result:
- task appears as `PENDING` then moves through worker states.
- artifacts are written under `.converge/runs/<timestamp>/`.

## Quickstart 2: Docker Compose (Postgres + API + Worker + UI)

```bash
docker-compose up --build
```

Services:
- API: `http://localhost:8080`
- UI: `http://localhost:3000`
- Postgres: `localhost:5432`

Verify:

```bash
python - <<'PY'
import requests
print(requests.get("http://localhost:8080/healthz", timeout=10).json())
print(requests.get("http://localhost:8080/api/tasks", timeout=10).status_code)
PY
```
