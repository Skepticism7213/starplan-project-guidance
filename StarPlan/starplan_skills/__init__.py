"""
StarPlan Loop - AI-Ready Skills for campus astronomy observation.

Core Skills:
    - target_resolve: Resolve target names to standard coordinates
    - observability_plan: Compute observability and generate observation plans
    - outreach_pack: Generate outreach activity packs from verified facts
    - observation_review: Compare plans with actual logs and revise next plans

Week 3 additions:
    - nl_parser: Natural language → StarPlanInput via Qwen
    - qwen_client: Qwen API wrapper with tool-calling support
    - runner: Three entry modes (structured / NL / chat orchestration)
"""

__version__ = "0.3.0"

from .runner import run_starplan, run_starplan_nl, run_starplan_chat
from .exceptions import TargetConfirmationRequired
from .nl_parser import parse_natural_language
from .qwen_client import call_qwen, call_qwen_json, call_qwen_chat
