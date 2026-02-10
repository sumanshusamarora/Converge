# Converge

**Converge helps multiple repositories that build one product collaborate, decide, and converge safely.**

Modern software systems are often built across multiple repositories—each owning different responsibilities like backend, frontend, infrastructure, mobile apps, or data pipelines. Converge is a coordination and governance tool that helps these repositories work together effectively without becoming a code synchronizer or autonomous refactoring engine.

## What Converge Is

Converge is a **multi-repository coordination tool** that:

- **Coordinates** changes across repositories with different responsibilities (e.g., API + Web + Mobile)
- **Surfaces** constraints and ownership boundaries early in the planning process
- **Proposes** responsibility splits based on repository capabilities and constraints
- **Enforces** bounded convergence to prevent endless debates
- **Escalates** to humans when judgment is needed (security, architecture, unclear ownership)
- **Generates** human-readable artifacts: summaries, responsibility matrices, and decision logs

## What Converge Is NOT

Converge explicitly does **not**:

- ❌ Sync duplicate repositories or mirror code between repos
- ❌ Automatically apply code changes to external repositories
- ❌ Run infinite agent debates or autonomous refactoring
- ❌ Replace human judgment on critical decisions
- ❌ Manage version control or deployment workflows

## How It Works (Conceptual Flow)

```
Input:     Goal + Multiple Repositories
    ↓
Collect:   Per-repository constraints
    ↓
Propose:   Responsibility split across repos
    ↓
Converge:  Bounded rounds (default: 2)
    ↓
Output:    Artifacts OR Escalation to Human
```

### Example Scenarios

**Scenario 1: Add discount code support**
- **Repos:** `api`, `web`, `mobile`
- **Converge identifies:**
  - API owns: discount validation, persistence, business logic
  - Web/Mobile own: UI for entering codes, client-side validation
- **Output:** Responsibility matrix + recommended implementation approach

**Scenario 2: Change authentication method**
- **Converge detects:** Security-critical change affecting all repos
- **Action:** Immediate escalation to HITL with options and risks

## Installation

```bash
# Clone the repository
git clone https://github.com/sumanshusamarora/Converge.git
cd Converge

# Install in development mode
pip install -e ".[dev]"
```

## Usage

### Basic Coordination Command

```bash
converge coordinate \
  --goal "Add discount_code support" \
  --repos api \
  --repos web \
  --repos mobile
```

### Options

- `--goal`: The high-level goal to achieve (required)
- `--repos`: Repository identifier (can be specified multiple times, at least one required)
- `--max-rounds`: Maximum convergence rounds (default: 2)
- `--output-dir`: Directory for artifacts (default: ./converge-output)
- `--log-level`: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Output Artifacts

Converge generates human-readable artifacts in the output directory:

1. **coordination-summary.md**: Complete session summary including:
   - Goal and status
   - Collected constraints per repository
   - Proposed responsibility split with rationale
   - Decisions made during convergence
   - Escalation reason (if applicable)

2. **responsibility-matrix.md**: Clear breakdown of which repository owns what

## MVP Scope Disclaimer

**This is an MVP implementation (v0.1.0).** Current limitations:

- Constraint collection is **stubbed** (returns placeholder constraints)
- Responsibility split uses **simple heuristics** (not AI-powered)
- Convergence is **simulated** (no actual repository interaction)
- No integration with version control systems
- No automated code generation or application

Future iterations will add:
- Real repository analysis (tech stack, APIs, ownership)
- AI-powered responsibility assignment
- Contract validation and version compatibility checks
- Integration with GitHub/GitLab for automated workflows
- Support for custom constraint plugins

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Architecture

```
src/converge/
├── cli/           # Command-line interface
├── core/          # Core configuration and logging
├── orchestration/ # Coordination logic and state management
└── utils/         # Shared utilities

tests/             # Test suite
```

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass (`pytest`)
2. Code is formatted (`ruff format .`)
3. No linting errors (`ruff check .`)
4. Type checking passes (`mypy src/`)
5. Documentation is updated for new features

## License

MIT License - see LICENSE file for details.

## Project Philosophy

Converge is built on these principles:

1. **Repositories are peers, not mirrors** - Each owns distinct responsibilities
2. **Early convergence over exhaustive debate** - Bounded rounds prevent analysis paralysis
3. **Human judgment for critical decisions** - AI assists, humans decide on security/architecture
4. **Artifacts over automation** - Produce plans and evidence, not automatic code changes
5. **Safety first** - Escalate when uncertain, validate before acting
