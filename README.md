# Agent Evaluation Lab (Project 03)

**Execution Tracing, Trajectory Scoring, Failure Taxonomy & Regression Benchmarking Suite.**

## Technical Focus (Phase 5 — Weeks 9–10)
- **Trace Ingestion**: Consumes OpenTelemetry spans and `axiom-runtime` `TraceEvent` timelines.
- **Tool-Call & Trajectory Scoring**: Evaluates tool selection accuracy, argument validity, and step efficiency.
- **Failure Taxonomy Classifier**: Deterministically buckets failures (`MODEL_TIMEOUT`, `TOOL_FAILURE`, `WORKER_INTERRUPTION`, `DUPLICATE_SUBMISSION`, `INVALID_TOOL_ARGUMENTS`, `APPROVAL_TIMEOUT`).
- **Regression Benchmark Suite**: 50–100 reproducible scenarios measuring execution success rate, recovery rate, duplicate execution rate (`0%` target), P50/P95 latency, and token cost.
