# Converge

Converge is a multi-repository coordination system that accepts tasks, runs bounded orchestration, escalates ambiguous decisions to HITL, and writes auditable run artifacts you can review or action.

Why Converge exists:
- keep cross-repo ownership decisions explicit
- provide a queue/worker model for repeatable orchestration runs
- produce artifacts (summary, matrix, run payload, prompt packs) for humans to execute safely

## Local quickstart (SQLite)

```bash
pip install -e ".[dev]"
export SQLALCHEMY_DATABASE_URI="sqlite:///./converge.db"
export CONVERGE_QUEUE_BACKEND="db"
export OPIK_TRACK_DISABLE="true"
converge server --port 8080
# in another terminal
converge worker
```

## Docker quickstart (Postgres + API + Worker + UI)

```bash
docker-compose up --build
```

- API: http://localhost:8080
- UI: http://localhost:3000

## Documentation

- [Overview](docs/index.md)
- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli.md)
- [Configuration](docs/configuration.md)
- [Tasks and HITL](docs/tasks-and-hitl.md)
- [Providers and Execution](docs/providers-and-execution.md)
- [UI](docs/ui.md)
- [Troubleshooting](docs/troubleshooting.md)

HITL and artifacts are first-class: when Converge cannot safely decide, tasks move to `HITL_REQUIRED`, and every run writes files under `.converge/runs/<timestamp>/`.
