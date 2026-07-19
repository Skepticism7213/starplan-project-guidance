"""
StarPlan Loop - Configuration loader.

Loads constraints from data/constraints_config.yaml and provides
typed access to observing constraint thresholds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Project root: two levels up from this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
RUNS_DIR = PROJECT_ROOT / "runs"
CATALOG_PATH = DATA_DIR / "built_in_catalog_v1.json"
LOCATIONS_PATH = DATA_DIR / "locations_v1.json"
CONSTRAINTS_PATH = DATA_DIR / "constraints_config.yaml"


def load_constraints() -> dict[str, Any]:
    """Load and return the observing constraints configuration."""
    if not CONSTRAINTS_PATH.exists():
        raise FileNotFoundError(f"Constraints config not found: {CONSTRAINTS_PATH}")
    with open(CONSTRAINTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_catalog() -> list[dict]:
    """Load the built-in target catalog."""
    import json

    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Catalog not found: {CATALOG_PATH}")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_locations() -> list[dict]:
    """Load the built-in location table."""
    import json

    if not LOCATIONS_PATH.exists():
        raise FileNotFoundError(f"Locations not found: {LOCATIONS_PATH}")
    with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_run_dir(run_id: str) -> Path:
    """Create and return the output directory for a given run."""
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
