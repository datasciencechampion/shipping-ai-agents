"""Score the shared v4.1 port slice on the golden set (same cases as medguard-eval)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from medguard.eval.run import _print_report
from medguard.eval.scoring import score_structured
from ports.slice import review_v41

_DEFAULT_GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden_set.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ports.run_eval",
        description="Score ports.slice.review_v41 on the MedGuard golden set.",
    )
    parser.add_argument("--golden", default=str(_DEFAULT_GOLDEN))
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: could not read golden set: {exc}", file=sys.stderr)
        return 2

    cases = data.get("cases", [])
    report = score_structured(cases, review_v41)
    _print_report(report, f"{data.get('name', args.golden)} [ports.slice v4.1]")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
