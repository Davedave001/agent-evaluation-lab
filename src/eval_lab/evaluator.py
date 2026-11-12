"""Trajectory evaluator, tool-call scorer, failure classifier, and regression comparator."""

from __future__ import annotations

import math
from typing import Counter, Dict, List

from eval_lab.schemas import (
    BenchmarkSummary,
    ExecutionTraceRecord,
    RegressionComparison,
    RunEvaluationResult,
    ScenarioExpectation,
)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return round(d0 + d1, 2)


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate LLM API cost using standard $1.25 / 1M input and $5.00 / 1M output rates."""
    cost = (prompt_tokens * 1.25 / 1_000_000.0) + (completion_tokens * 5.00 / 1_000_000.0)
    return round(cost, 6)


class TrajectoryEvaluator:
    """Grades an ExecutionTraceRecord against a ScenarioExpectation."""

    @staticmethod
    def evaluate_run(
        trace: ExecutionTraceRecord,
        expectation: ScenarioExpectation,
    ) -> RunEvaluationResult:
        executed_keys: List[str] = [
            tc.idempotency_key for tc in trace.tool_calls if not tc.was_replayed_from_cache
        ]
        key_counts = Counter(executed_keys)
        duplicate_executions = sum(count - 1 for count in key_counts.values() if count > 1)

        actual_tools = [tc.tool_name for tc in trace.tool_calls]
        if not expectation.expected_tools_in_order:
            tool_accuracy = 1.0 if len(actual_tools) == 0 else 0.0
        else:
            matches = 0
            for idx, expected_name in enumerate(expectation.expected_tools_in_order):
                if idx < len(trace.tool_calls) and trace.tool_calls[idx].tool_name == expected_name:
                    req_keys = expectation.required_arg_keys.get(expected_name, [])
                    actual_args = trace.tool_calls[idx].arguments
                    if all(k in actual_args for k in req_keys):
                        matches += 1
            tool_accuracy = matches / len(expectation.expected_tools_in_order)

        if trace.total_steps <= expectation.max_allowed_steps:
            efficiency = 1.0
        else:
            efficiency = max(
                0.0,
                1.0
                - (trace.total_steps - expectation.max_allowed_steps)
                / expectation.max_allowed_steps,
            )

        isolation_ok = (
            trace.state_isolation_verified
            if expectation.expect_concurrent_isolation
            else True
        )

        outcome_matched = (
            trace.succeeded == expectation.expect_success
            and trace.failure_category == expectation.expected_failure_category
            and (not expectation.expect_recovery or trace.recovered_from_interruption)
            and duplicate_executions == 0
            and isolation_ok
        )

        trajectory_score = round(
            0.5 * tool_accuracy + 0.3 * efficiency + (0.2 if outcome_matched else 0.0), 4
        )

        return RunEvaluationResult(
            run_id=trace.run_id,
            scenario_id=trace.scenario_id,
            category=expectation.category,
            passed=outcome_matched and tool_accuracy >= 0.99,
            trajectory_score=trajectory_score,
            tool_call_accuracy=round(tool_accuracy, 4),
            step_efficiency_score=round(efficiency, 4),
            duplicate_tool_executions=duplicate_executions,
            concurrent_isolation_passed=isolation_ok,
            classified_failure=trace.failure_category,
            latency_ms=trace.latency_ms,
            estimated_cost_usd=estimate_cost_usd(trace.prompt_tokens, trace.completion_tokens),
        )

    @staticmethod
    def summarize_benchmark(
        suite_name: str,
        traces: List[ExecutionTraceRecord],
        expectations: Dict[str, ScenarioExpectation],
    ) -> BenchmarkSummary:
        results: List[RunEvaluationResult] = []
        latencies: List[float] = []
        memories: List[float] = []
        failure_dist: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}

        expected_success_total = 0
        expected_success_passed = 0
        interrupted_total = 0
        recovered_total = 0
        concurrent_total = 0
        concurrent_isolated = 0
        total_tool_calls = 0
        succeeded_tool_calls = 0
        total_duplicates = 0

        for trace in traces:
            exp = expectations[trace.scenario_id]
            res = TrajectoryEvaluator.evaluate_run(trace, exp)
            results.append(res)
            latencies.append(trace.latency_ms)
            memories.append(trace.memory_overhead_kb)
            category_counts[exp.category] = category_counts.get(exp.category, 0) + 1

            if trace.failure_category != "NONE":
                failure_dist[trace.failure_category] = (
                    failure_dist.get(trace.failure_category, 0) + 1
                )

            if exp.expect_success:
                expected_success_total += 1
                if trace.succeeded:
                    expected_success_passed += 1

            if trace.was_interrupted:
                interrupted_total += 1
                if trace.recovered_from_interruption and trace.succeeded:
                    recovered_total += 1

            if exp.expect_concurrent_isolation or trace.concurrent_batch_id is not None:
                concurrent_total += 1
                if trace.state_isolation_verified and trace.succeeded:
                    concurrent_isolated += 1

            for tc in trace.tool_calls:
                total_tool_calls += 1
                if tc.succeeded:
                    succeeded_tool_calls += 1

            total_duplicates += res.duplicate_tool_executions

        total = len(traces) or 1
        exec_rate = (
            (expected_success_passed / expected_success_total)
            if expected_success_total
            else 1.0
        )
        rec_rate = (recovered_total / interrupted_total) if interrupted_total else 1.0
        dup_rate = (total_duplicates / total_tool_calls) if total_tool_calls else 0.0
        tool_rate = (succeeded_tool_calls / total_tool_calls) if total_tool_calls else 1.0
        conc_rate = (concurrent_isolated / concurrent_total) if concurrent_total else 1.0
        mean_traj = sum(r.trajectory_score for r in results) / total
        mean_mem = sum(memories) / total
        total_cost = sum(r.estimated_cost_usd for r in results)

        return BenchmarkSummary(
            suite_name=suite_name,
            total_scenarios=len(traces),
            execution_success_rate=round(exec_rate, 4),
            recovery_success_rate=round(rec_rate, 4),
            duplicate_execution_rate=round(dup_rate, 4),
            tool_call_success_rate=round(tool_rate, 4),
            concurrent_isolation_rate=round(conc_rate, 4),
            concurrent_runs_tested=concurrent_total,
            mean_trajectory_score=round(mean_traj, 4),
            p50_latency_ms=percentile(latencies, 50.0),
            p95_latency_ms=percentile(latencies, 95.0),
            mean_memory_overhead_kb=round(mean_mem, 2),
            total_cost_usd=round(total_cost, 6),
            category_counts=category_counts,
            failure_distribution=failure_dist,
        )

    @staticmethod
    def compare_runs(
        baseline: BenchmarkSummary,
        candidate: BenchmarkSummary,
    ) -> RegressionComparison:
        success_delta = round(
            candidate.execution_success_rate - baseline.execution_success_rate, 4
        )
        recovery_delta = round(
            candidate.recovery_success_rate - baseline.recovery_success_rate, 4
        )
        dup_delta = round(
            candidate.duplicate_execution_rate - baseline.duplicate_execution_rate, 4
        )
        p95_delta = round(candidate.p95_latency_ms - baseline.p95_latency_ms, 2)

        regression = (
            success_delta < 0.0
            or recovery_delta < 0.0
            or dup_delta > 0.0
            or candidate.concurrent_isolation_rate < baseline.concurrent_isolation_rate
        )
        return RegressionComparison(
            baseline_suite=baseline.suite_name,
            candidate_suite=candidate.suite_name,
            success_rate_delta=success_delta,
            recovery_rate_delta=recovery_delta,
            duplicate_rate_delta=dup_delta,
            p95_latency_delta_ms=p95_delta,
            regression_detected=regression,
        )
