"""Command-line entry point for MedGuard v0.

Usage:
    medguard --case examples/renal_overdose.json
    cat case.json | medguard            # read a case from stdin
    MEDGUARD_FAKE=1 medguard --case ...  # force deterministic offline mode
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .agent import review
from .capstone import review_end_to_end
from .config import Config

_DISCLAIMER = (
    "MedGuard is a teaching artifact, NOT a medical device. "
    "Do not use for real clinical decisions."
)


def _load_case(path: str | None) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    case = json.loads(raw)
    if not isinstance(case, dict):
        raise ValueError("A case must be a JSON object.")
    return case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="medguard",
        description="MedGuard v0 — naive medication-safety review (teaching artifact).",
    )
    parser.add_argument("--case", help="Path to a case JSON file (defaults to stdin).")
    parser.add_argument("--fake", action="store_true", help="Force deterministic offline mode.")
    parser.add_argument("--end-to-end", action="store_true",
                        help="Run the finished v5 pipeline (Chapter 19) and print a "
                             "structured verdict + redacted audit record as JSON.")
    parser.add_argument("--version", action="version", version=f"medguard {__version__} (v0)")
    args = parser.parse_args(argv)

    try:
        case = _load_case(args.case)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: could not read case: {exc}", file=sys.stderr)
        return 2

    config = Config.from_env()
    if args.fake:
        config = Config(provider=config.provider, model=config.model, api_key=config.api_key, fake=True)

    print(f"! {_DISCLAIMER}", file=sys.stderr)

    if args.end_to_end:
        # The full production path: structured, grounded, guarded, audited.
        print("# MedGuard v5 end-to-end review\n", file=sys.stderr)
        result = review_end_to_end(case)
        print(json.dumps({
            "review": result.review.to_dict(),
            "escalated": result.escalated,
            "escalation_reason": result.escalation_reason,
            "audit": result.audit,
        }, indent=2, default=str))
        # A dangerous case that isn't approved is the safe outcome -> exit 0.
        return 0

    mode = "fake/offline" if config.fake else f"{config.provider}:{config.model}"
    print(f"# MedGuard v0 review  (mode: {mode})\n", file=sys.stderr)

    print(review(case, config))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
