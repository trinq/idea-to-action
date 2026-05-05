#!/usr/bin/env python3
"""Run the eval suite on initial cases.

Usage:
    python scripts/run_evals.py
    python scripts/run_evals.py --path custom_evals.json
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from idea_to_action.evals.runner import load_eval_cases, print_report, run_all_evals


def main() -> int:
    parser = argparse.ArgumentParser(description="Run idea-to-action eval suite.")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to custom eval cases JSON file.",
    )
    args = parser.parse_args()

    print("== Eval Suite: idea-to-action ==\n")

    cases = load_eval_cases(args.path)
    reports = run_all_evals(cases)
    passed, failed = print_report(reports)

    if failed > 0:
        print(f"\n{failed} eval(s) failed.")
        return 1

    print("\nAll evals passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
