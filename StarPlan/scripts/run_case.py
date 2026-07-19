#!/usr/bin/env python3
"""
StarPlan Loop - Run a single case from an example JSON file.

Usage:
    python scripts/run_case.py examples/case_01_m31_jinan.json
    python scripts/run_case.py examples/case_02_unfavorable_window.json
    python scripts/run_case.py examples/case_03_observation_review.json
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from starplan_skills.runner import run_starplan


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_case.py <case_json_file>")
        print("Example: python scripts/run_case.py examples/case_01_m31_jinan.json")
        sys.exit(1)

    case_file = PROJECT_ROOT / sys.argv[1]
    if not case_file.exists():
        print(f"Error: File not found: {case_file}")
        sys.exit(1)

    with open(case_file, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    print(f"{'='*60}")
    print(f"StarPlan Loop - Running: {case_file.name}")
    print(f"{'='*60}")
    print()

    result = run_starplan(input_data)

    print()
    print(f"{'='*60}")
    print(f"Run ID: {result['run_id']}")
    print(f"Output: {result['run_dir']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
