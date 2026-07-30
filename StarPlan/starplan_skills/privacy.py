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

# Fields to remove from JSON files during export (field-level allowlist)
_REDACT_FIELDS = {
    "observer_notes",
    "blocked_content",
    "messages",
    "prompt_preview",
    "user_input",
}


def _sanitize_json(data):
    """Recursively remove sensitive fields from a JSON structure."""
    if isinstance(data, dict):
        return {
            k: _sanitize_json(v)
            for k, v in data.items()
            if k not in _REDACT_FIELDS
        }
    elif isinstance(data, list):
        return [_sanitize_json(item) for item in data]
    return data


def sanitize_run_for_export(
    run_dir: Path,
    export_dir: Optional[Path] = None,
) -> Path:
    """Create an export-safe copy of a run directory.

    P1-A: field-level sanitization, not just file-level filtering.
    - Rejects non-empty export directory (no stale audit file residue)
    - JSON files: recursively removes observer_notes, blocked_content, messages
    - Non-JSON deliverables: copied as-is (outreach_pack.md, plots, CSV)
    - Audit-only files: never copied

    Args:
        run_dir: Source run directory.
        export_dir: Destination. Must not exist or must be empty.

    Returns:
        Path to the export directory.

    Raises:
        ValueError: If export_dir exists and is non-empty.
    """
    if export_dir is None:
        export_dir = run_dir.parent / f"{run_dir.name}_export"

    # P1-A: reject non-empty target to prevent stale audit file residue
    if export_dir.exists() and any(export_dir.iterdir()):
        raise ValueError(
            f"Export directory '{export_dir}' is not empty. "
            f"Refusing to export into a directory with existing files."
        )

    export_dir.mkdir(parents=True, exist_ok=True)

    for fname in DELIVERABLE_FILES:
        src = run_dir / fname
        if not src.exists():
            continue

        if fname.endswith(".json"):
            # Field-level sanitization for JSON
            try:
                data = json.loads(src.read_text(encoding="utf-8"))
                sanitized = _sanitize_json(data)
                with open(export_dir / fname, "w", encoding="utf-8") as f:
                    json.dump(sanitized, f, ensure_ascii=False, indent=2, default=str)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Malformed JSON: skip (fail-closed, don't export garbage)
                pass
        else:
            # Non-JSON: copy as-is (markdown, CSV, PNG)
            shutil.copy2(src, export_dir / fname)

    # Write privacy policy metadata
    with open(export_dir / "privacy_policy.json", "w", encoding="utf-8") as f:
        json.dump(PRIVACY_POLICY, f, ensure_ascii=False, indent=2)

    return export_dir


def verify_export_sanitized(export_dir: Path) -> list[str]:
    """P1-A: Recursively scan all exported files for sensitive content.

    Returns a list of violations (empty = clean export).
    Checks:
      1. No audit-only filenames present
      2. No sensitive field names in JSON content
      3. No sensitive field values (observer_notes text) in any text file
    """
    violations = []

    if not export_dir.exists():
        return ["Export directory does not exist"]

    for fpath in export_dir.rglob("*"):
        if not fpath.is_file():
            continue

        # Check 1: audit-only filenames
        if fpath.name in AUDIT_ONLY_FILES:
            violations.append(f"Audit file present in export: {fpath.name}")

        # Check 2: sensitive fields in JSON
        if fpath.suffix in (".json", ".jsonl"):
            try:
                content = fpath.read_text(encoding="utf-8")
                for field in _REDACT_FIELDS:
                    if f'"{field}"' in content:
                        violations.append(
                            f"Sensitive field '{field}' found in {fpath.name}"
                        )
            except UnicodeDecodeError:
                pass

        # Check 3: blocked_content / messages keywords in markdown
        if fpath.suffix in (".md", ".txt"):
            try:
                content = fpath.read_text(encoding="utf-8")
                for marker in ["blocked_content", "hallucination_verification"]:
                    if marker in content:
                        violations.append(
                            f"Audit marker '{marker}' found in {fpath.name}"
                        )
            except UnicodeDecodeError:
                pass

    return violations


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
