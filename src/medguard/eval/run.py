"""Run the MedGuard eval harness against the golden set and print a report.

Usage:
    medguard-eval --golden evals/golden_set.json
    MEDGUARD_FAKE=1 medguard-eval            # deterministic, offline

Exit code is non-zero if there is *any* unsafe approval, so this can gate a CI
pipeline: no build ships if the agent approves something dangerous.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..agent import review
from ..config import Config
from ..pipeline import review_case
from .scoring import SEVERITY_ORDER, Report, score, score_structured

_DEFAULT_GOLDEN = Path(__file__).resolve().parents[3] / "evals" / "golden_set.json"


def _print_report(report: Report, dataset_name: str) -> None:
    print(f"\n=== MedGuard eval: {dataset_name} ===")
    print(f"Cases: {report.total}")
    print(f"Overall exact-match accuracy: {report.accuracy:.0%} "
          f"({report.correct}/{report.total})")

    print("\nPer-severity breakdown (this is what actually matters):")
    print(f"  {'severity':<10}{'cases':>7}{'unsafe approvals':>20}")
    for sev in SEVERITY_ORDER:
        bucket = report.by_severity().get(sev, {"total": 0, "unsafe_approvals": 0})
        if bucket["total"] == 0:
            continue
        print(f"  {sev:<10}{bucket['total']:>7}{bucket['unsafe_approvals']:>20}")

    unsafe = report.unsafe_approvals
    print(f"\nUNSAFE APPROVALS: {len(unsafe)} "
          f"(high-severity: {len(report.high_severity_unsafe)})")
    for r in unsafe:
        print(f"  [{r.max_severity:>8}] {r.case_id}: "
              f"expected {r.expected}, agent said {r.predicted}")

    if report.passed:
        print("\nPASS: no unsafe approvals.")
    else:
        print("\nFAIL: the agent approved cases that are not safe to approve.")
        print("      Aggregate accuracy looked fine; the tail did not.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="medguard-eval",
        description="Score MedGuard against the golden set (stratified by severity).",
    )
    parser.add_argument("--golden", default=str(_DEFAULT_GOLDEN),
                        help="Path to the golden-set JSON.")
    parser.add_argument("--fake", action="store_true",
                        help="Force deterministic offline mode.")
    parser.add_argument("--agent", choices=["v0", "v3", "v41"], default="v0",
                        help="Which agent to score: v0 (naive prose), v3 "
                             "(structured, no guardrails), v41 (structured + dose veto).")
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: could not read golden set: {exc}", file=sys.stderr)
        return 2

    config = Config.from_env()
    if args.fake:
        config = Config(provider=config.provider, model=config.model,
                        api_key=config.api_key, fake=True)

    cases = data.get("cases", [])
    if args.agent == "v0":
        report = score(cases, lambda case: review(case, config))
    else:
        use_guardrails = args.agent == "v41"
        report = score_structured(
            cases, lambda case: review_case(case, guardrails=use_guardrails))
    _print_report(report, f"{data.get('name', args.golden)} [{args.agent}]")

    # Gate: any unsafe approval fails the run.
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
