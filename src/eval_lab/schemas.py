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
    expected_failure_category: str = "NONE"
    max_allowed_steps: int = 6


class RunEvaluationResult(BaseModel):
    """Detailed evaluation scorecard for a single agent run."""

    run_id: str
    scenario_id: str
    passed: bool
    trajectory_score: float = Field(ge=0.0, le=1.0)
    tool_call_accuracy: float = Field(ge=0.0, le=1.0)
    step_efficiency_score: float = Field(ge=0.0, le=1.0)
    duplicate_tool_executions: int = 0
    classified_failure: str = "NONE"
    latency_ms: float
    estimated_cost_usd: float


class BenchmarkSummary(BaseModel):
    """Aggregate portfolio metrics across the 50–100 scenario benchmark dataset."""

    suite_name: str
    total_scenarios: int
    execution_success_rate: float
    recovery_success_rate: float
    duplicate_execution_rate: float
    tool_call_success_rate: float
    mean_trajectory_score: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_memory_overhead_kb: float
    total_cost_usd: float
    failure_distribution: Dict[str, int] = Field(default_factory=dict)
