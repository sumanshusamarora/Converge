# How Converge Runs

This guide explains Converge as a simple story: a task is submitted, a worker processes it, Converge plans the work, optionally executes it (when allowed), writes artifacts, and pauses for human decisions when needed.

For exact environment-variable defaults, use [Configuration](configuration.md). This page focuses on the end-to-end flow.

## 1) High-Level Overview

```text
User / API / CLI
        ↓
      Task
        ↓
      Queue
        ↓
      Worker
        ↓
  Planning Phase
        ↓
(Optional) Execution Phase
        ↓
  Artifacts + Logs
        ↓
HITL (if needed)
        ↓
  Resume / Complete
```

## 2) Step-by-Step Lifecycle

### Step 1 — Task Creation

A task can be created from the CLI, API, or UI.

Converge records the task in the configured queue backend so it can be processed reliably.

### Step 2 — Worker Picks Up Task

A worker polls the queue, claims available tasks, and starts processing.

As the task moves through the run, its status is updated so you can track progress.

### Step 3 — Planning Phase

Converge generates proposals for the requested goal across the target repositories.

Typical planning outputs include repository-level plans and handoff artifacts that humans can review or use directly.

Planning may use LLM-based generation or deterministic heuristics, depending on configuration and key availability. If Converge cannot safely decide, it can request human input.

### Step 4 — Optional Execution Phase

Execution only happens when execution mode and provider settings allow it.

In execution-capable runs, Converge may run commands and (when explicitly enabled) apply changes. Safety gates still apply, so risky or out-of-bounds outcomes can be stopped for review.

### Step 5 — Artifact Generation

Every run produces artifacts so the process is auditable and easy to resume.

What you can expect:

- Plan documents
- Prompt packs
- Execution logs (when execution is used)
- Summary outputs for run review

### Step 6 — HITL Interruption (if required)

When human input is required, the task enters `HITL_REQUIRED`.

After you submit a resolution, the task can be returned to the queue and resumed by a worker.

### Step 7 — Final States

A task ends in one of these user-visible states:

- `SUCCEEDED`
- `FAILED`
- `HITL_REQUIRED`
- `CANCELLED`

## 3) Where Things Run

Converge can be used in different environments, with clear responsibilities:

- **CLI**: convenient way to submit and manage runs from a terminal.
- **Server**: accepts API requests and exposes task/run data when HTTP workflows are used.
- **UI**: optional interface for browsing tasks, artifacts, and HITL actions.
- **Worker**: the component that actually processes queued tasks end-to-end.

If there is one thing to remember: **the worker drives task execution and lifecycle progress**.

## 4) Example Walkthrough

**Goal:** “Add new API endpoint across backend and frontend repositories.”

1. A developer submits the task through the UI (or CLI/API).
2. The task is queued and picked up by a worker.
3. Planning generates repository plans (for backend and frontend), plus prompt-style artifacts and summaries.
4. If execution is enabled for this run, Converge may perform allowed actions. If execution is disabled, artifacts still provide a complete handoff.
5. If a safety threshold is exceeded or a decision is unclear, the run moves to `HITL_REQUIRED`.
6. A human resolves the question, and the worker resumes the task.
7. The task finishes as `SUCCEEDED` (or another final state), with artifacts preserved for review.

## 5) Key Takeaways

- Planning and execution are separate phases.
- Execution is optional and safety-gated.
- HITL is a first-class part of normal operation.
- All runs produce artifacts you can review.
- The worker is responsible for processing tasks.
- You can run the same lifecycle through CLI, API/server, or UI.
