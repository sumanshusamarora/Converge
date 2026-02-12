# Execution & Modes Explained

This page gives you a **first-time-user mental model** for how Converge decides what to plan, what to execute, and when to ask for human input.

If you want the full variable catalog, use [Configuration](configuration.md). This page focuses on **how the pieces interact**.

## 1) Big Picture (Simple Mental Model)

Think of Converge as operating across four independent axes:

- **A) Planning vs Execution**
  - **Planning** = generating proposals and artifacts.
  - **Execution** = actually modifying repositories or running commands.
- **B) Interactive vs Headless**
  - **Interactive** = requires a human terminal (TTY).
  - **Headless** = worker/CI/container safe (no TTY required).
- **C) Provider**
  - `codex` or `copilot`.
- **D) Proposal generation path**
  - **LLM-backed** or **heuristic**.

In short: these switches are related, but not the same thing.

```text
Task → Plan → (Optional) Execute → Artifacts → HITL → Resume
```

## 2) Planning Modes

By default, Converge is safe-first and plan-first.

- Repository plan generation uses the selected provider (`codex` or `copilot`).
- Responsibility split proposal generation uses OpenAI when available, with heuristic fallback.
- You can force heuristic proposal generation even when an API key exists.

### Responsibility proposal decision tree

```text
If CONVERGE_NO_LLM=true  → heuristic
Else if OPENAI_API_KEY exists → LLM planning
Else → heuristic
```

### Variables that affect planning

| Variable | What it does |
|---|---|
| `CONVERGE_NO_LLM` | Forces heuristic responsibility proposal generation. |
| `OPENAI_API_KEY` | Enables LLM responsibility proposals when `CONVERGE_NO_LLM` is not set to true. |
| `CONVERGE_CODING_AGENT` | Chooses repository planning provider (`codex` or `copilot`). |
| `CONVERGE_CODING_AGENT_MODEL` | Forces one coding-agent model for repository planning. |
| `CONVERGE_CODING_AGENT_MODEL_CANDIDATES` | Optional fallback order for coding-agent model selection. |

## 3) Execution Modes (Primary Switch)

`CONVERGE_EXECUTION_MODE` is the primary high-level execution policy:

- `plan`: planning only
- `interactive`: execution-capable with TTY
- `headless`: execution-capable without TTY

### What each mode allows

| Mode | What it allows | What it forbids | Best fit |
|---|---|---|---|
| `plan` | Proposal generation + artifacts only | No file edits, no command execution | Safe default, architecture/planning work |
| `interactive` | Execution-capable workflows in a live terminal | Non-interactive worker-style operation | Local developer sessions, guided/manual runs |
| `headless` | Non-TTY automation flows | TTY-only interactive behavior | CI, workers, Docker, background automation |

### Quick capability comparison

| Mode        | Edits files | Runs commands | Requires TTY | Safe for worker |
|-------------|------------|--------------|--------------|-----------------|
| plan        | No         | No           | No           | Yes             |
| interactive | Yes        | Yes          | Yes          | No              |
| headless    | Yes*       | Yes          | No           | Yes             |

\* Headless file-apply behavior is supported for Codex apply when enabled.

## 4) Provider Behavior (Codex vs Copilot)

Providers decide **who plans** and **which execution paths are valid**.

### Codex

- Can plan.
- Can execute in interactive or headless paths.
- Must have `CONVERGE_CODEX_APPLY=true` to actually modify repositories.

### Copilot

- Can plan.
- Does not execute code.
- Intended for VS Code-driven workflows.

### Provider × mode matrix

| Provider | plan | interactive | headless |
|----------|------|-------------|----------|
| codex    | ✅   | ✅          | ✅ (if apply enabled) |
| copilot  | ✅   | ❌          | ❌ |

## 5) Codex Apply Safety Gates

When using Codex apply, Converge adds explicit safeguards before and after execution.

### Key gates and controls

| Variable | Purpose |
|---|---|
| `CONVERGE_CODEX_APPLY` | Master switch. Must be `true` for Codex apply to modify repos. |
| `CONVERGE_REQUIRE_GIT_CLEAN` | Requires clean git state before execution-capable flow. |
| `CONVERGE_ALLOW_DIRTY` | Allows Codex apply on dirty working trees when explicitly enabled. |
| `CONVERGE_CREATE_BRANCH` | Auto-creates a `converge/...` branch before applying changes. |
| `CONVERGE_MAX_CHANGED_FILES` | Optional cap on changed file count. |
| `CONVERGE_MAX_DIFF_LINES` | Optional cap on diff line count. |
| `CONVERGE_MAX_DIFF_BYTES` | Optional cap on diff byte size. |

If any configured threshold is exceeded, the run becomes **`HITL_REQUIRED`** (not `FAILED`).

### Example

You run in `headless` mode with `CONVERGE_CODEX_APPLY=true`.

- Codex modifies 50 files.
- `CONVERGE_MAX_CHANGED_FILES=25`.
- Result: execution stops and task status becomes **`HITL_REQUIRED`** so a human can review and decide the next step.

## 6) Common Config Combinations (Practical Recipes)

### A) Safe Local Planning Only

```bash
CONVERGE_EXECUTION_MODE=plan
# OPENAI_API_KEY is optional
```

Use when you want plans/artifacts without any execution risk.

### B) VS Code Copilot Workflow

```bash
CONVERGE_CODING_AGENT=copilot
CONVERGE_EXECUTION_MODE=plan
```

Use when you want Copilot-oriented plan artifacts that a developer applies manually in VS Code.

### C) CI Verification (No Edits)

```bash
CONVERGE_EXECUTION_MODE=headless
CONVERGE_CODEX_APPLY=false
```

Use for non-interactive checks and planning outputs without applying patches.

### D) Controlled Automated Apply

```bash
CONVERGE_EXECUTION_MODE=headless
CONVERGE_CODEX_APPLY=true
CONVERGE_MAX_CHANGED_FILES=25
CONVERGE_MAX_DIFF_LINES=800
CONVERGE_MAX_DIFF_BYTES=120000
```

Use for bounded automation with explicit review thresholds.

## 7) Precedence Rules (Very Important)

1. If execution mode is `plan`, nothing executes.
2. Copilot is planning-only (no execution path in interactive or headless mode).
3. Codex apply requires explicit `CONVERGE_CODEX_APPLY=true`.
4. `CONVERGE_NO_LLM` overrides `OPENAI_API_KEY`.
5. Threshold violations trigger `HITL_REQUIRED`, not failure.

## 8) FAQ

### Why is nothing executing?

Most often, one of these is true:

- `CONVERGE_EXECUTION_MODE=plan`
- Provider/mode combination does not support your execution path
- For Codex apply, `CONVERGE_CODEX_APPLY` is not set to `true`

### Why did my task become `HITL_REQUIRED` after execution?

Typical reasons:

- Safety thresholds were exceeded (`files`, `lines`, or `bytes`)
- Converge needs a human decision before continuing

This is a controlled stop, not a crash.

### Why is Copilot not executing anything?

Copilot is currently planning-only in Converge. For automated execution flows, use Codex with execution settings enabled.

### What happens if `OPENAI_API_KEY` is missing?

Converge falls back to heuristic planning automatically. You still get plans and artifacts; they are just generated without LLM calls.

---

For exact defaults and every environment variable, see [Configuration](configuration.md).
