"""Schemas for Execution Traces, Scenario Expectations, Run Evaluations, and Benchmark Reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecordedToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    was_replayed_from_cache: bool = False
    succeeded: bool = True


class ExecutionTraceRecord(BaseModel):
    """Normalized execution trace collected from Axiom Runtime for evaluation."""

    run_id: str
    scenario_id: str
    succeeded: bool
    recovered_from_interruption: bool = False
    was_interrupted: bool = False
    concurrent_batch_id: Optional[str] = None
    state_isolation_verified: bool = True
    failure_category: str = "NONE"
    tool_calls: List[RecordedToolCall] = Field(default_factory=list)
    total_steps: int = 1
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    memory_overhead_kb: float = 128.0
    final_output: Optional[str] = None


class ScenarioExpectation(BaseModel):
    """Ground-truth expectation for a reproducible benchmark scenario."""

    scenario_id: str
    category: str
    expected_tools_in_order: List[str] = Field(default_factory=list)
    required_arg_keys: Dict[str, List[str]] = Field(default_factory=dict)
    expect_success: bool = True
    expect_recovery: bool = False
    expect_concurrent_isolation: bool = False
    expected_failure_category: str = "NONE"
    max_allowed_steps: int = 6


class RunEvaluationResult(BaseModel):
    """Detailed evaluation scorecard for a single agent run."""

    run_id: str
    scenario_id: str
    category: str
    passed: bool
    trajectory_score: float = Field(ge=0.0, le=1.0)
    tool_call_accuracy: float = Field(ge=0.0, le=1.0)
    step_efficiency_score: float = Field(ge=0.0, le=1.0)
    duplicate_tool_executions: int = 0
    concurrent_isolation_passed: bool = True
    classified_failure: str = "NONE"
    latency_ms: float
    estimated_cost_usd: float


class BenchmarkSummary(BaseModel):
    """Aggregate portfolio metrics across the 100-scenario benchmark dataset."""

    suite_name: str
    total_scenarios: int
    execution_success_rate: float
    recovery_success_rate: float
    duplicate_execution_rate: float
    tool_call_success_rate: float
    concurrent_isolation_rate: float
    concurrent_runs_tested: int
    mean_trajectory_score: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_memory_overhead_kb: float
    total_cost_usd: float
    category_counts: Dict[str, int] = Field(default_factory=dict)
    failure_distribution: Dict[str, int] = Field(default_factory=dict)


class RegressionComparison(BaseModel):
    """Comparison report between a baseline and candidate benchmark run."""

    baseline_suite: str
    candidate_suite: str
    success_rate_delta: float
    recovery_rate_delta: float
    duplicate_rate_delta: float
    p95_latency_delta_ms: float
    regression_detected: bool
