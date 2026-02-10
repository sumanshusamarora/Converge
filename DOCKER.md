# Converge Docker Deployment

This directory contains Docker Compose configuration for running Converge in a containerized environment.

## Services

The docker-compose setup includes four services:

1. **postgres** - PostgreSQL database for task queue persistence
2. **converge-api** - FastAPI server exposing REST endpoints
3. **converge-worker** - Background worker polling and executing tasks
4. **converge-frontend** - Next.js web UI

## Quick Start

1. **Set environment variables** (optional):
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

2. **Start all services**:
   ```bash
   docker-compose up -d
   ```

3. **Access the UI**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8080
   - Health check: http://localhost:8080/healthz

4. **View logs**:
   ```bash
   docker-compose logs -f converge-api
   docker-compose logs -f converge-worker
   docker-compose logs -f converge-frontend
   ```

5. **Stop all services**:
   ```bash
   docker-compose down
   ```

## Environment Variables

The following environment variables can be configured:

### Required
- `OPENAI_API_KEY` - OpenAI API key (optional but required for LLM-based execution)

### Optional
- `SQLALCHEMY_DATABASE_URI` - Database connection string (defaults to Postgres in docker-compose)
- `CONVERGE_QUEUE_BACKEND` - Queue backend (defaults to "db")
- `CONVERGE_OUTPUT_DIR` - Directory for artifacts (defaults to "/artifacts" in containers)
- `OPIK_TRACK_DISABLE` - Disable Opik tracing (defaults to "true" in docker-compose)

## Volumes

Two persistent volumes are created:

1. **postgres-data** - Stores PostgreSQL data
2. **converge-artifacts** - Stores task execution artifacts (.converge directory)

To reset the database and artifacts:
```bash
docker-compose down -v
```

## Development

For local development without Docker:

1. **Start PostgreSQL** (or use SQLite):
   ```bash
   export SQLALCHEMY_DATABASE_URI="sqlite:///./converge.db"
   ```

2. **Start API server**:
   ```bash
   converge server --port 8080
   ```

3. **Start worker**:
   ```bash
   converge worker
   ```

4. **Start frontend**:
   ```bash
   cd src/frontend
   npm install
   npm run dev
   ```

## Architecture

```
┌─────────────┐         ┌─────────────┐
│  Frontend   │────────>│   API       │
│  (Next.js)  │         │  (FastAPI)  │
│  :3000      │         │  :8080      │
└─────────────┘         └─────┬───────┘
                              │
                              │ Queue
                              v
                        ┌─────────────┐
                        │  Postgres   │
                        │  :5432      │
                        └─────┬───────┘
                              ^
                              │
                        ┌─────┴───────┐
                        │   Worker    │
                        │  (Poller)   │
                        └─────────────┘
```

## API Endpoints

- `GET /healthz` - Health check
- `GET /api/tasks` - List tasks (with optional status filter)
- `GET /api/tasks/{id}` - Get task details
- `POST /api/tasks` - Create a new task
- `POST /api/tasks/{id}/resolve` - Resolve a HITL task
- `POST /api/tasks/{id}/cancel` - Cancel a task
- `GET /api/runs/{run_id}/files` - List artifacts for a run
- `GET /api/runs/{run_id}/files/{path}` - Download artifact file

## Frontend Features

- **Task List**: View all tasks with status filtering
- **Task Details**: View complete task information and request details
- **Create Task**: Submit new coordination tasks
- **HITL Resolution**: Resolve tasks requiring human input
- **Artifact Viewer**: View summary and download handoff pack files

## Troubleshooting

### Database connection issues
```bash
# Check if postgres is ready
docker-compose ps postgres
docker-compose logs postgres

# Restart the postgres service
docker-compose restart postgres
```

### Worker not processing tasks
```bash
# Check worker logs
docker-compose logs -f converge-worker

# Verify queue backend setting
docker-compose exec converge-worker env | grep CONVERGE_QUEUE_BACKEND
```

### Frontend can't reach API
```bash
# Check CORS configuration
docker-compose logs converge-api | grep CORS

# Verify API is accessible
curl http://localhost:8080/healthz
```

## Production Considerations

For production deployment:

1. Use a managed PostgreSQL instance (e.g., AWS RDS, Cloud SQL)
2. Set up proper secrets management (not environment variables)
3. Configure reverse proxy (nginx/Traefik) for HTTPS
4. Set up monitoring and logging (Prometheus, Grafana, etc.)
5. Configure resource limits in docker-compose.yml
6. Use Docker secrets instead of environment variables for sensitive data
7. Set up automated backups for PostgreSQL
