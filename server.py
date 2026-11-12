"""FastAPI Service & Standalone Server Entrypoint for Agent Evaluation Lab (Port 8003)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn
from fastapi import FastAPI
from eval_lab.benchmark import (
    format_benchmark_markdown,
    generate_reproducible_benchmark_suite,
)
from eval_lab.evaluator import TrajectoryEvaluator
from eval_lab.schemas import BenchmarkSummary

app = FastAPI(
    title="Agent Evaluation Lab API",
    version="0.2.0",
    description="100-Scenario Benchmark Runner, Trajectory Scorer & Failure Taxonomy Service",
)


@app.get("/health")
def health() -> dict:
    return {"service": "agent-evaluation-lab", "status": "healthy", "scenarios": 100}


@app.get("/benchmark/summary", response_model=BenchmarkSummary)
def run_benchmark_summary() -> BenchmarkSummary:
    traces, expectations = generate_reproducible_benchmark_suite()
    return TrajectoryEvaluator.summarize_benchmark(
        suite_name="Axiom Runtime v0.2 — 100-Scenario Reliability Suite",
        traces=traces,
        expectations=expectations,
    )


@app.get("/benchmark/markdown")
def run_benchmark_markdown() -> dict:
    summary = run_benchmark_summary()
    return {"markdown": format_benchmark_markdown(summary)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="info")
