# Opik Trace Walkthrough (Heuristic Planning): `019c4f38-fee4-7c11-9b60-f2d276a23fad`

This document explains how Converge trace data is stored in Opik and walks through all 20 spans for one real run.

Note: this trace was captured before span deduplication changes. At capture time, both node decorators and LangGraph app tracking were enabled, which produced paired node spans.

## Trace summary

- Trace ID: `019c4f38-fee4-7c11-9b60-f2d276a23fad`
- Project: `Converge`
- Root span name: `LangGraph`
- Start (UTC): `2026-02-12 00:21:01.284123+00:00`
- End (UTC): `2026-02-12 00:23:56.128965+00:00`
- Total spans: `20`

## How Converge writes this trace

Converge writes spans from two instrumentation paths:

1. Node-level decorators:
- `@opik_track("collect_constraints_node")`
- `@opik_track("propose_split_node")`
- `@opik_track("agent_plan_node")`
- `@opik_track("decide_node")`
- `@opik_track("hitl_interrupt_node")`
- `@opik_track("write_artifacts_node")`

2. LangGraph-level wrapper:
- `track_langgraph_app(...)` wraps the compiled graph execution.

Because both are active, each logical graph node appears as two spans:
- an outer LangGraph runtime span
- an inner decorated function span

LLM calls add additional child spans (`ChatOpenAI`).

## How Opik stores this run

At minimum, this run is represented as:

- 1 trace record:
  - `id`, `name`, `start_time`, `end_time`, tags
- 20 span records:
  - `id`, `trace_id`, `parent_span_id`, `name`, `start_time`, `end_time`
  - `input`, `output`, `metadata`, tags

Important relationships:

- `trace_id` groups all spans into this run.
- `parent_span_id` creates the execution tree.
- node outputs carry evolving orchestration state (`round`, `status`, `repo_plans`, `events`).

## Step-by-step: all 20 spans

Legend:
- Duration is wall time of that span.
- Parent shows tree linkage.
- `status/round` is read from span output state when present.

1. Span `019c4f38-fee6-7142-b1f0-7bd66c8ece24`
- Name: `collect_constraints_node`
- Parent: `none`
- Duration: `0.591 ms`
- What happened: repository constraints/signals collected.
- State signal: pre-decision state initialized.

2. Span `019c4f38-fee7-74df-8a26-b810f6b402fa`
- Name: `collect_constraints_node`
- Parent: `019c4f38-fee6-7142-b1f0-7bd66c8ece24`
- Duration: `0.238 ms`
- What happened: inner decorated function span for the same node.

3. Span `019c4f38-fee8-70af-b153-87d7b4d909b5`
- Name: `propose_split_node`
- Parent: `none`
- Duration: `75500.881 ms`
- What happened: round-1 split proposal stage started.

4. Span `019c4f38-feea-7226-a299-ad6ef8f5c136`
- Name: `propose_split_node`
- Parent: `019c4f38-fee8-70af-b153-87d7b4d909b5`
- Duration: `75500.515 ms`
- What happened: inner proposal function span for round 1.

5. Span `019c4f39-0034-7d5e-b4b4-8f4c81e64ec8`
- Name: `ChatOpenAI`
- Parent: `019c4f38-fee8-70af-b153-87d7b4d909b5`
- Duration: `75166.057 ms`
- What happened: LLM generated proposal JSON.
- Model metadata: provider `openai`, model `gpt-5`.
- Token usage: prompt `86`, completion `3611`, total `3697`.

6. Span `019c4f3a-25d3-723f-99fd-9463f89d9492`
- Name: `agent_plan_node`
- Parent: `none`
- Duration: `1.776 ms`
- What happened: repository agent plans generated.

7. Span `019c4f3a-25d5-7dcc-bff5-7801f5ad96b9`
- Name: `agent_plan_node`
- Parent: `019c4f3a-25d3-723f-99fd-9463f89d9492`
- Duration: `1.323 ms`
- What happened: inner plan span; one repo plan became `HITL_REQUIRED`.

8. Span `019c4f3a-25d5-74a3-8534-9fe3759e0f2d`
- Name: `decide_node`
- Parent: `none`
- Duration: `1.006 ms`
- What happened: decision after round 1.
- State signal: `status=HITL_REQUIRED`, `round=1/2`.

9. Span `019c4f3a-25d6-742d-b1b0-56fb77d256f4`
- Name: `decide_node`
- Parent: `019c4f3a-25d5-74a3-8534-9fe3759e0f2d`
- Duration: `0.073 ms`
- What happened: inner decision function span.

10. Span `019c4f3a-25d7-713b-8418-85c1521f81f3`
- Name: `route_after_decide`
- Parent: `019c4f3a-25d5-74a3-8534-9fe3759e0f2d`
- Duration: `0.177 ms`
- What happened: conditional router selected `propose_split_node` (retry).

11. Span `019c4f3a-25d8-7fdf-80ba-23326d7ef851`
- Name: `propose_split_node`
- Parent: `none`
- Duration: `99324.591 ms`
- What happened: round-2 split proposal stage started.

12. Span `019c4f3a-25d9-773f-bb73-5b480b930166`
- Name: `propose_split_node`
- Parent: `019c4f3a-25d8-7fdf-80ba-23326d7ef851`
- Duration: `99323.995 ms`
- What happened: inner proposal function span for round 2.

13. Span `019c4f3a-25da-7bef-b303-858e5d9d713d`
- Name: `ChatOpenAI`
- Parent: `019c4f3a-25d8-7fdf-80ba-23326d7ef851`
- Duration: `99321.948 ms`
- What happened: second LLM proposal.
- Model metadata: provider `openai`, model `gpt-5`.
- Token usage: prompt `86`, completion `4986`, total `5072`.

14. Span `019c4f3b-a9d4-7338-8fd1-5132309d95d7`
- Name: `agent_plan_node`
- Parent: `none`
- Duration: `5.195 ms`
- What happened: second planning pass across repos.

15. Span `019c4f3b-a9da-7993-9a15-91ce2cf9f8fc`
- Name: `agent_plan_node`
- Parent: `019c4f3b-a9d4-7338-8fd1-5132309d95d7`
- Duration: `4.261 ms`
- What happened: inner plan span; backend repo still `HITL_REQUIRED`.

16. Span `019c4f3b-a9da-72bb-bbe3-40d5a3c2faa2`
- Name: `decide_node`
- Parent: `none`
- Duration: `1.441 ms`
- What happened: final decision after max rounds.
- State signal: `status=HITL_REQUIRED`, `round=2/2`.

17. Span `019c4f3b-a9db-751c-9bf0-dae9957ead4b`
- Name: `decide_node`
- Parent: `019c4f3b-a9da-72bb-bbe3-40d5a3c2faa2`
- Duration: `0.110 ms`
- What happened: inner decision span.

18. Span `019c4f3b-a9dc-7d6f-8798-b9a0898a2e6f`
- Name: `route_after_decide`
- Parent: `019c4f3b-a9da-72bb-bbe3-40d5a3c2faa2`
- Duration: `0.257 ms`
- What happened: router selected `write_artifacts_node` (stop loop).

19. Span `019c4f3b-a9dd-7a64-93f4-6c269904c739`
- Name: `write_artifacts_node`
- Parent: `none`
- Duration: `4.071 ms`
- What happened: summary/matrix/run artifacts written.
- State signal: terminal orchestration status persisted as `HITL_REQUIRED`.

20. Span `019c4f3b-a9de-789b-ac7b-245284cc8166`
- Name: `write_artifacts_node`
- Parent: `019c4f3b-a9dd-7a64-93f4-6c269904c739`
- Duration: `3.336 ms`
- What happened: inner artifact-write span for the same terminal node.

## What this trace says about system behavior

- Orchestration flow is correct for `--hil-mode conditional` with `--max-rounds 2`.
- Two full rounds occurred.
- Round 1 hit `HITL_REQUIRED` and retried.
- Round 2 hit `HITL_REQUIRED` again and exited to artifact writing.
- Dominant latency is LLM proposal generation (`ChatOpenAI`), not graph or DB logic.

## Local exported copies used to build this doc

- `.converge/trace-inspection/019c4f38-fee4-7c11-9b60-f2d276a23fad/trace.json`
- `.converge/trace-inspection/019c4f38-fee4-7c11-9b60-f2d276a23fad/spans.json`
- `.converge/trace-inspection/019c4f38-fee4-7c11-9b60-f2d276a23fad/timeline.json`
