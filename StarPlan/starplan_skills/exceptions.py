"""
StarPlan Loop - Custom exceptions for pipeline control flow.

These exceptions carry structured data so callers (UI, CLI, chat orchestrator)
can present meaningful choices to the user rather than silently proceeding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import ResolvedTarget


class TargetConfirmationRequired(Exception):
    """
    Raised when target_resolve returns an ambiguous result that requires
    human selection before the pipeline can proceed.

    This enforces the project rule: "名称歧义时必须要求人工选择，不得自动
    选择低置信度结果" (skills.yaml, project plan, kickoff report).

    Attributes:
        resolved: The ResolvedTarget with requires_confirmation=True,
                  including the candidates list for the caller to display.
    """

    def __init__(self, message: str, resolved: "ResolvedTarget"):
        super().__init__(message)
        self.resolved = resolved

    @property
    def candidates(self):
        """Shortcut to the candidate list."""
        return self.resolved.candidates or []

    def format_candidates(self) -> str:
        """Format candidates as a human-readable numbered list."""
        lines = []
        for i, c in enumerate(self.candidates, 1):
            lines.append(
                f"  {i}. {c.standard_name} ({c.target_type}, "
                f"confidence={c.confidence:.2f})"
            )
        return "\n".join(lines)
