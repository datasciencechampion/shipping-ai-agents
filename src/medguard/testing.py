"""Snapshot / trace-replay helpers for testing a non-deterministic agent.

The idea: capture the agent's output for a set of cases once, commit it as a
*snapshot*, then in tests replay those recorded outputs to detect regressions —
without calling a live model. This lets us test everything downstream of the
model (extraction, scoring, gating) deterministically and offline.

At v1.1 the "trace" is just the model's text output per case. When full
structured tracing arrives in Chapter 5 (v2), the same pattern replays complete
execution traces, not just final text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def record_outputs(cases: list[dict], run_agent: Callable[[dict], str]) -> dict[str, str]:
    """Run ``run_agent`` over cases, keyed by ``case_id`` — the raw snapshot."""
    return {case["case_id"]: run_agent(case) for case in cases}


def save_snapshot(path: str | Path, snapshot: dict[str, str]) -> None:
    Path(path).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def load_snapshot(path: str | Path) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_cases(golden_path: str | Path) -> list[dict]:
    return json.loads(Path(golden_path).read_text(encoding="utf-8")).get("cases", [])
