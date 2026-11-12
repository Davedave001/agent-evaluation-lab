"""Tests for Project 03: Agent Evaluation Lab (Trajectory Scorer & 60-Scenario Benchmark Suite)."""

from __future__ import annotations

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


def test_60_scenario_reproducible_benchmark_suite() -> None:
    """Verify the 60-scenario benchmark dataset achieves 100% execution & recovery rate and 0% duplicate rate."""
    traces, expectations = generate_reproducible_benchmark_suite()
    assert len(traces) == 60

    summary = TrajectoryEvaluator.summarize_benchmark(
        suite_name="Axiom Runtime v0.1 Reliability Suite",
        traces=traces,
        expectations=expectations,
    )

    assert summary.total_scenarios == 60
    assert summary.execution_success_rate == 1.0
    assert summary.recovery_success_rate == 1.0
    assert summary.duplicate_execution_rate == 0.0
    assert summary.tool_call_success_rate == 1.0
    assert summary.p95_latency_ms >= summary.p50_latency_ms > 0
    assert summary.failure_distribution == {
        "INVALID_TOOL_ARGUMENTS": 5,
        "APPROVAL_TIMEOUT": 5,
        "MODEL_TIMEOUT": 5,
    }

    md = format_benchmark_markdown(summary)
    assert "Duplicate Tool Execution Rate**: `0.00%`" in md


def test_duplicate_side_effect_detection_penalizes_run() -> None:
    """If a buggy runtime executes the same idempotency_key twice without cache replay,
    TrajectoryEvaluator must flag duplicate_tool_executions > 0 and fail the run.
    """
    exp = ScenarioExpectation(
        scenario_id="scen-dup-bug",
        category="idempotency_audit",
        expected_tools_in_order=["publish_report_tool"],
        expect_success=True,
    )
    buggy_trace = ExecutionTraceRecord(
        run_id="run-buggy-1",
        scenario_id="scen-dup-bug",
        succeeded=True,
        total_steps=2,
        latency_ms=210.0,
        tool_calls=[
            RecordedToolCall(
                tool_name="publish_report_tool",
                arguments={"title": "R1"},
                idempotency_key="same-key-123",
                was_replayed_from_cache=False,
            ),
            RecordedToolCall(
                tool_name="publish_report_tool",
                arguments={"title": "R1"},
                idempotency_key="same-key-123",
                was_replayed_from_cache=False,  # Executed externally twice!
            ),
        ],
    )

    result = TrajectoryEvaluator.evaluate_run(buggy_trace, exp)
    assert result.duplicate_tool_executions == 1
    assert result.passed is False
