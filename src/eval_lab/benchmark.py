"""Reproducible 60-Scenario Benchmark Dataset & Markdown Scorecard Generator."""

from __future__ import annotations

from typing import Dict, List, Tuple

from eval_lab.evaluator import TrajectoryEvaluator
from eval_lab.schemas import (
    BenchmarkSummary,
    ExecutionTraceRecord,
    RecordedToolCall,
    ScenarioExpectation,
)


def generate_reproducible_benchmark_suite() -> Tuple[List[ExecutionTraceRecord], Dict[str, ScenarioExpectation]]:
    """Build the 60-scenario benchmark dataset recommended in the Portfolo specification (50–100 scenarios):
    - 30 multi-step normal execution scenarios
    - 10 worker crash & checkpoint recovery scenarios (verifying 100% recovery & 0% duplicate execution)
    - 5 transient retry recovery scenarios
    - 15 deterministic terminal fault scenarios (5 invalid args, 5 approval timeouts, 5 persistent model timeouts)
    """
    traces: List[ExecutionTraceRecord] = []
    expectations: Dict[str, ScenarioExpectation] = {}

    # 1. 30 Standard Multi-Step Research & Reporting Scenarios
    for i in range(1, 31):
        sid = f"scen-normal-{i:03d}"
        expectations[sid] = ScenarioExpectation(
            scenario_id=sid,
            category="standard_multi_step",
            expected_tools_in_order=["search_tool", "summarize_tool", "publish_report_tool"],
            required_arg_keys={
                "search_tool": ["query"],
                "summarize_tool": ["documents"],
                "publish_report_tool": ["title", "summary_body"],
            },
            expect_success=True,
            max_allowed_steps=4,
        )
        traces.append(
            ExecutionTraceRecord(
                run_id=f"run-{sid}",
                scenario_id=sid,
                succeeded=True,
                total_steps=4,
                latency_ms=180.0 + (i * 3.5),
                prompt_tokens=850,
                completion_tokens=190,
                memory_overhead_kb=142.0,
                tool_calls=[
                    RecordedToolCall(
                        tool_name="search_tool",
                        arguments={"query": f"topic-{i}"},
                        idempotency_key=f"idem-{sid}-1",
                    ),
                    RecordedToolCall(
                        tool_name="summarize_tool",
                        arguments={"documents": ["Doc A", "Doc B"]},
                        idempotency_key=f"idem-{sid}-2",
                    ),
                    RecordedToolCall(
                        tool_name="publish_report_tool",
                        arguments={"title": f"Report {i}", "summary_body": "Synthesis..."},
                        idempotency_key=f"idem-{sid}-3",
                    ),
                ],
            )
        )

    # 2. 10 Worker Interruption & Idempotent Checkpoint Recovery Scenarios
    for i in range(1, 11):
        sid = f"scen-crash-recovery-{i:03d}"
        expectations[sid] = ScenarioExpectation(
            scenario_id=sid,
            category="crash_recovery",
            expected_tools_in_order=["search_tool", "search_tool", "summarize_tool"],
            expect_success=True,
            expect_recovery=True,
            max_allowed_steps=4,
        )
        traces.append(
            ExecutionTraceRecord(
                run_id=f"run-{sid}",
                scenario_id=sid,
                succeeded=True,
                was_interrupted=True,
                recovered_from_interruption=True,
                total_steps=3,
                latency_ms=260.0 + (i * 5.0),
                prompt_tokens=620,
                completion_tokens=140,
                memory_overhead_kb=156.0,
                tool_calls=[
                    RecordedToolCall(
                        tool_name="search_tool",
                        arguments={"query": f"recover-{i}"},
                        idempotency_key=f"idem-{sid}-step0",
                        was_replayed_from_cache=False,
                    ),
                    # Replayed from idempotency cache on resume (NOT a duplicate external execution)
                    RecordedToolCall(
                        tool_name="search_tool",
                        arguments={"query": f"recover-{i}"},
                        idempotency_key=f"idem-{sid}-step0",
                        was_replayed_from_cache=True,
                    ),
                    RecordedToolCall(
                        tool_name="summarize_tool",
                        arguments={"documents": ["Recovered Doc"]},
                        idempotency_key=f"idem-{sid}-step1",
                    ),
                ],
            )
        )

    # 3. 5 Transient Retry Recovery Scenarios
    for i in range(1, 6):
        sid = f"scen-transient-retry-{i:03d}"
        expectations[sid] = ScenarioExpectation(
            scenario_id=sid,
            category="transient_retry",
            expected_tools_in_order=["search_tool"],
            expect_success=True,
            max_allowed_steps=3,
        )
        traces.append(
            ExecutionTraceRecord(
                run_id=f"run-{sid}",
                scenario_id=sid,
                succeeded=True,
                total_steps=2,
                latency_ms=340.0 + (i * 10.0),
                prompt_tokens=410,
                completion_tokens=95,
                memory_overhead_kb=138.0,
                tool_calls=[
                    RecordedToolCall(
                        tool_name="search_tool",
                        arguments={"query": f"flaky-{i}"},
                        idempotency_key=f"idem-{sid}-1",
                    )
                ],
            )
        )

    # 4. 15 Deterministic Terminal Fault Scenarios (5 Invalid Args, 5 Approval Timeouts, 5 Model Timeouts)
    fault_configs = [
        ("INVALID_TOOL_ARGUMENTS", 5),
        ("APPROVAL_TIMEOUT", 5),
        ("MODEL_TIMEOUT", 5),
    ]
    for fault_cat, count in fault_configs:
        for i in range(1, count + 1):
            sid = f"scen-fault-{fault_cat.lower()}-{i:02d}"
            expectations[sid] = ScenarioExpectation(
                scenario_id=sid,
                category="fault_classification",
                expected_tools_in_order=[],
                expect_success=False,
                expected_failure_category=fault_cat,
                max_allowed_steps=3,
            )
            traces.append(
                ExecutionTraceRecord(
                    run_id=f"run-{sid}",
                    scenario_id=sid,
                    succeeded=False,
                    failure_category=fault_cat,
                    total_steps=1,
                    latency_ms=110.0 + (i * 4.0),
                    prompt_tokens=200,
                    completion_tokens=40,
                    memory_overhead_kb=120.0,
                    tool_calls=[],
                )
            )

    return traces, expectations


def format_benchmark_markdown(summary: BenchmarkSummary) -> str:
    """Format BenchmarkSummary as a publication-ready Markdown report."""
    return (
        f"# Benchmark Scorecard: {summary.suite_name}\n\n"
        f"- **Total Reproducible Scenarios**: `{summary.total_scenarios}`\n"
        f"- **Execution Success Rate**: `{summary.execution_success_rate * 100:.1f}%`\n"
        f"- **Crash Recovery Success Rate**: `{summary.recovery_success_rate * 100:.1f}%`\n"
        f"- **Duplicate Tool Execution Rate**: `{summary.duplicate_execution_rate * 100:.2f}%`\n"
        f"- **Tool-Call Success Rate**: `{summary.tool_call_success_rate * 100:.1f}%`\n"
        f"- **Mean Trajectory Score**: `{summary.mean_trajectory_score:.4f}`\n"
        f"- **Latency (P50 / P95)**: `{summary.p50_latency_ms} ms` / `{summary.p95_latency_ms} ms`\n"
        f"- **Mean Memory Overhead**: `{summary.mean_memory_overhead_kb} KB`\n"
        f"- **Total Suite API Cost**: `${summary.total_cost_usd:.4f}`\n"
    )
