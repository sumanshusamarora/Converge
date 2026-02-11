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
- Postgres: internal-only by default (no host port published)

## How Converge Works

Converge runs tasks through a queue-and-worker lifecycle: submit a task, generate plans and artifacts, optionally execute when policy allows, and escalate to HITL when human decisions are needed. This keeps automation bounded while preserving clear audit trails for every run.

See [How Converge Runs](docs/how-converge-runs.md) for a complete explanation.


## Documentation

- [Overview](docs/index.md)
- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli.md)
- [How Converge Runs](docs/how-converge-runs.md)
- [Configuration](docs/configuration.md)
- [Tasks and HITL](docs/tasks-and-hitl.md)
- [Providers and Execution](docs/providers-and-execution.md)
- [Execution & Modes Explained](docs/execution-and-modes.md)
- [UI](docs/ui.md)
- [Troubleshooting](docs/troubleshooting.md)

HITL and artifacts are first-class: when Converge cannot safely decide, tasks move to `HITL_REQUIRED`, and every run writes files under `.converge/runs/<timestamp>/`.
