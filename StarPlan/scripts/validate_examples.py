#!/usr/bin/env python3
"""
StarPlan Loop - Validate all example JSON files against the input schema.

Usage:
    python scripts/validate_examples.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from starplan_skills.schemas import StarPlanInput


def validate_case(path: Path) -> bool:
    """Validate a single case file against StarPlanInput schema."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        StarPlanInput(**data)
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main():
    examples_dir = PROJECT_ROOT / "examples"
    if not examples_dir.exists():
        print(f"Examples directory not found: {examples_dir}")
        sys.exit(1)

    files = sorted(examples_dir.glob("*.json"))
    if not files:
        print("No JSON files found in examples/")
        sys.exit(1)

    passed = 0
    failed = 0

    for f in files:
        ok = validate_case(f)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {f.name}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed, {len(files)} total")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
