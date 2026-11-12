"""Tests for Project 03: Agent Evaluation Lab (100-Scenario Benchmark Suite & Regression Comparator)."""

from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path

from eval_lab.benchmark import (
    format_benchmark_markdown,
    generate_reproducible_benchmark_suite,
)
from eval_lab.evaluator import TrajectoryEvaluator
from eval_lab.schemas import (
    ExecutionTraceRecord,
    RecordedToolCall,
    ScenarioExpectation,
)


def test_100_scenario_reproducible_benchmark_suite() -> None:
    """Verify the expanded 100-scenario benchmark dataset covers all 7 metrics from the Portfolo spec."""
    traces, expectations = generate_reproducible_benchmark_suite()
    assert len(traces) == 100

    summary = TrajectoryEvaluator.summarize_benchmark(
        suite_name="Axiom Runtime v0.2 — 100-Scenario Reliability Suite",
        traces=traces,
        expectations=expectations,
    )

    assert summary.total_scenarios == 100
    assert summary.execution_success_rate == 1.0
    assert summary.recovery_success_rate == 1.0
    assert summary.duplicate_execution_rate == 0.0
    assert summary.tool_call_success_rate == 1.0
    assert summary.concurrent_isolation_rate == 1.0
    assert summary.concurrent_runs_tested == 20
    assert summary.p95_latency_ms >= summary.p50_latency_ms > 0
    assert summary.category_counts == {
        "standard_multi_step": 40,
        "crash_recovery": 15,
        "transient_retry": 10,
        "concurrent_isolation": 20,
        "fault_classification": 15,
    }

    md = format_benchmark_markdown(summary)
    assert "| **Total Scenarios** | `100` |" in md
    assert "| **Duplicate Execution Rate** | `0.00%` |" in md


def test_duplicate_side_effect_detection_and_regression_comparison() -> None:
    """Verify duplicate tool execution detection and baseline-vs-candidate regression comparison."""
    traces, expectations = generate_reproducible_benchmark_suite()
    baseline = TrajectoryEvaluator.summarize_benchmark("baseline-v1", traces, expectations)

    # Introduce a regression in candidate where one scenario duplicates a tool execution
    regressed_traces = [t.model_copy(deep=True) for t in traces]
    regressed_traces[0].tool_calls.append(
        RecordedToolCall(
            tool_name="search_tool",
            arguments={"query": "topic-1"},
            idempotency_key=regressed_traces[0].tool_calls[0].idempotency_key,
            was_replayed_from_cache=False,
        )
    )
    candidate = TrajectoryEvaluator.summarize_benchmark("candidate-v2-buggy", regressed_traces, expectations)

    comparison = TrajectoryEvaluator.compare_runs(baseline, candidate)
    assert comparison.duplicate_rate_delta > 0.0
    assert comparison.regression_detected is True


def test_live_concurrent_runs_against_axiom_runtime() -> None:
    """Execute 10 concurrent agent runs in parallel threads against AxiomRuntime to verify real scheduling isolation."""
    axiom_src = str(Path(__file__).resolve().parents[2] / "axiom-runtime" / "src")
    if axiom_src not in sys.path:
        sys.path.insert(0, axiom_src)

    from axiom.demo.research_agent import (
        build_research_tool_registry,
        create_research_agent_definition,
        default_research_agent_script,
    )
    from axiom.engine.runner import AxiomRunner
    from axiom.gateway.adapter import ScriptedModelAdapter
    from axiom.schemas.domain import RunStatus, TaskSubmission
    from axiom.state.store import InMemoryStateStore

    store = InMemoryStateStore()
    side_effects = {}
    runner = AxiomRunner(
        store=store,
        model_adapter=ScriptedModelAdapter(default_research_agent_script),
        tool_registry=build_research_tool_registry(side_effects),
    )
    runner.register_agent(create_research_agent_definition())

    def run_single_task(idx: int) -> RunStatus:
        run, created = runner.submit_task(
            TaskSubmission(
                idempotency_key=f"live-concurrent-{idx:03d}",
                agent_name="research-and-reporting-agent",
                goal=f"Concurrent research task #{idx}",
            )
        )
        assert created is True
        paused = runner.execute_run(run.run_id)
        completed = runner.approve_tool_call(paused.run_id, decided_by=f"approver-{idx}")
        return completed.status

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(run_single_task, range(10)))

    assert all(s == RunStatus.COMPLETED for s in statuses)
