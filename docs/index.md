# Converge

Converge coordinates work across peer repositories by generating plans, tracking tasks in a queue, and escalating to human-in-the-loop (HITL) decisions when ownership or risk is unclear.

## What Converge is

- A coordination layer for multi-repo work.
- A task queue + worker system that runs bounded orchestration.
- An artifact generator (summaries, responsibility matrix, contract checks, run metadata, and per-repo plan packs).

## What Converge is not

- Not a repo sync/mirroring tool.
- Not a guaranteed auto-implementation engine.
- Not a replacement for human review on ambiguous or risky decisions.

## Key terms

- **Task**: Queue item containing `goal`, `repos`, and orchestration options.
- **Run**: One workflow execution for a task. Runs write files under `.converge/runs/<timestamp>/` by default.
- **Artifact**: Output file created during a run (for example `summary.md` or `run.json`).
- **HITL**: Human-in-the-loop escalation state (`HITL_REQUIRED`) when Converge needs input.
- **Provider**: Planning adapter used per repository (`codex` or `copilot`).
- **Execution mode**: Policy setting (`plan`, `interactive`, `headless`) controlling safety/runtime expectations for execution-capable integrations.

## Example trace walkthroughs

- [Opik Trace Walkthrough (Heuristic Planning)](opik-trace-walkthrough-heuristic.md)
- [Opik Trace Walkthrough (Codex Enabled)](opik-trace-walkthrough-codex-enabled.md)
