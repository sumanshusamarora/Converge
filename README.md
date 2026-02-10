# Converge

Converge is an open-source framework for coordinated, multi-repository software delivery with AI agents. It focuses on bounded orchestration, explicit contracts, and human-in-the-loop checkpoints.

## Project goals

- Provide safe orchestration primitives for multi-agent workflows.
- Keep API contracts observable and diffable.
- Preserve evidence-first development with tests and reproducible checks.

## Development setup

1. Create and activate Python 3.11+ virtual environment.
2. Install development dependencies:
   ```bash
   pip install -e .[dev]
   ```
3. Run quality checks:
   ```bash
   ruff check .
   ruff format .
   mypy
   pytest
   ```

## CLI usage

Display help:

```bash
converge --help
```

Show version:

```bash
converge --version
```

Run contract diff:

```bash
converge contract-diff --old old_contract.json --new new_contract.json
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
