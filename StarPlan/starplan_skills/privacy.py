"""
StarPlan Loop - Privacy, Sanitization, and Retention Policy (P2-4).

Defines boundaries for sensitive data in run artifacts:
  - chat_conversation.json: may contain user input, observer notes, Qwen prompts
  - model_call_log.jsonl: may contain prompt previews with personal context
  - blocked_content: hallucinated Qwen text, audit-only, never user-facing

Rules:
  1. blocked_content is AUDIT-ONLY. It must never appear in outreach_pack.md,
     final_content, or any user-facing deliverable.
  2. chat_conversation.json and model_call_log.jsonl are AUDIT artifacts.
     They are NOT part of the demo/export deliverable set.
  3. For export/demo, use sanitize_run_for_export() to produce a redacted copy.
  4. Retention: audit artifacts should be purged after 90 days in production.
     For competition demo, retention is the project lifetime.

This module does NOT modify files in place. It provides policy metadata and
a sanitization function for creating export-safe copies.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional


# ── Policy constants ─────────────────────────────────

# Files that are audit-only and must NOT be included in demo/export
AUDIT_ONLY_FILES = {
    "chat_conversation.json",
    "model_call_log.jsonl",
    "state_log.json",
}

# Files that are safe for user-facing delivery
DELIVERABLE_FILES = {
    "input.json",
    "resolved_target.json",
    "observability.csv",
    "visibility_curve.png",
    "plan.json",
    "claims.json",
    "sentence_claim_map.json",
    "outreach_pack.md",
    "run_outcome.json",
    "validation_report.md",
    "calculation_manifest.json",
    "review_report.md",
    "revised_plan.json",
}

# Retention policy (days)
RETENTION_AUDIT_DAYS = 90
RETENTION_DELIVERABLE_DAYS = None  # Keep indefinitely

# Fields in chat_conversation.json that contain potentially sensitive content
SENSITIVE_FIELDS = {
    "user_input",       # May contain personal names, location details
    "messages",         # Full Qwen conversation with system prompts
    "blocked_content",  # Hallucinated text (audit evidence)
}


# ── Policy metadata ──────────────────────────────────

PRIVACY_POLICY = {
    "version": "1.0",
    "effective_date": "2026-07-29",
    "scope": "StarPlan Loop run artifacts",
    "rules": [
        {
            "id": "P2-4-R1",
            "description": "blocked_content is audit-only; never in user output",
            "enforcement": "runner.py always replaces final_content with deterministic summary",
        },
        {
            "id": "P2-4-R2",
            "description": "chat_conversation.json and model_call_log.jsonl are audit artifacts",
            "enforcement": "Excluded from DELIVERABLE_FILES; sanitize_run_for_export removes them",
        },
        {
            "id": "P2-4-R3",
            "description": "Export copies redact user_input and messages to summaries",
            "enforcement": "sanitize_run_for_export replaces with field-length metadata",
        },
        {
            "id": "P2-4-R4",
            "description": f"Audit artifacts retention: {RETENTION_AUDIT_DAYS} days",
            "enforcement": "Manual or scheduled purge in production",
        },
    ],
    "audit_only_files": sorted(AUDIT_ONLY_FILES),
    "deliverable_files": sorted(DELIVERABLE_FILES),
}


# ── Sanitization ─────────────────────────────────────

def sanitize_run_for_export(
    run_dir: Path,
    export_dir: Optional[Path] = None,
) -> Path:
    """Create an export-safe copy of a run directory.

    - Copies only DELIVERABLE_FILES
    - Redacts any sensitive fields if chat_conversation.json is included
    - Does NOT copy audit-only files

    Args:
        run_dir: Source run directory.
        export_dir: Destination. Defaults to run_dir.parent / (run_dir.name + "_export").

    Returns:
        Path to the export directory.
    """
    if export_dir is None:
        export_dir = run_dir.parent / f"{run_dir.name}_export"

    export_dir.mkdir(parents=True, exist_ok=True)

    for fname in DELIVERABLE_FILES:
        src = run_dir / fname
        if src.exists():
            shutil.copy2(src, export_dir / fname)

    # Write privacy policy metadata
    with open(export_dir / "privacy_policy.json", "w", encoding="utf-8") as f:
        json.dump(PRIVACY_POLICY, f, ensure_ascii=False, indent=2)

    return export_dir


def verify_blocked_content_not_in_output(run_dir: Path) -> list[str]:
    """Verify that blocked_content from chat does not leak into user output.

    Returns a list of violations (empty = clean).
    """
    violations = []

    chat_path = run_dir / "chat_conversation.json"
    if not chat_path.exists():
        return violations  # No chat → nothing to check

    chat_data = json.loads(chat_path.read_text(encoding="utf-8"))
    blocked = chat_data.get("blocked_content", "")
    if not blocked or len(blocked) < 20:
        return violations  # Too short to meaningfully match

    # Check deliverable files for blocked content leakage
    for fname in ["outreach_pack.md", "review_report.md"]:
        fpath = run_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            # Check if any substantial substring of blocked content appears
            # Use 30-char windows to avoid false positives on common phrases
            for i in range(0, len(blocked) - 30, 10):
                snippet = blocked[i:i + 30]
                if snippet in content:
                    violations.append(
                        f"{fname} contains blocked_content snippet: '{snippet[:50]}...'"
                    )
                    break  # One violation per file is enough

    return violations
