"""
StarPlan Loop - Skill 1: target_resolve

Resolves a target name (Chinese, English, Messier, NGC, alias) into
a standard astronomical target with coordinates, type, and metadata.

Uses the built-in catalog (built_in_catalog_v1.json) as the primary
data source. Does NOT depend on any online service.
"""

from __future__ import annotations

import json
from typing import Optional

from .config import CATALOG_PATH
from .schemas import ResolvedTarget, TargetCandidate


def _load_catalog() -> list[dict]:
    """Load the built-in catalog from disk."""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_query(query: str) -> str:
    """Normalize the query string for matching."""
    return query.strip().lower().replace(" ", "").replace("_", "")


def _match_catalog_entry(query: str, entry: dict) -> float:
    """
    Score how well a query matches a catalog entry.

    Returns a confidence score between 0 and 1.
    """
    norm_query = _normalize_query(query)
    standard = _normalize_query(entry["standard_name"])

    # Exact match on standard name -> confidence 1.0
    if norm_query == standard:
        return 1.0

    # Match on aliases — check ALL aliases and return the best score
    best_alias_score = 0.0
    for alias in entry.get("aliases", []):
        norm_alias = _normalize_query(alias)
        # Exact alias match (highest priority, can short-circuit)
        if norm_query == norm_alias:
            return 0.95
        # Query is contained in alias (e.g. "三角座" in "三角座星系")
        # Require query length >= 30% of alias length to avoid spurious short-substring matches
        if len(norm_query) >= 2 and norm_query in norm_alias and len(norm_query) >= len(norm_alias) * 0.3:
            best_alias_score = max(best_alias_score, 0.85)
        # Alias is contained in query (e.g. "triangulum" in "triangulum galaxy xyz")
        elif len(norm_alias) >= 2 and norm_alias in norm_query:
            best_alias_score = max(best_alias_score, 0.80)

    if best_alias_score > 0:
        return best_alias_score

    # Partial / prefix match: query is a prefix of standard name (e.g., "M3" matches "M31")
    if standard.startswith(norm_query) and len(norm_query) >= 1:
        return 0.3  # Low confidence, will likely be ambiguous

    return 0.0


def resolve_target(
    target_name: str,
    target_type: Optional[str] = None,
) -> ResolvedTarget:
    """
    Resolve a target name into a standard astronomical target.

    Args:
        target_name: The name to resolve (Chinese, English, M-number, NGC, etc.)
        target_type: Optional type hint to disambiguate (deep_sky, star, etc.)

    Returns:
        ResolvedTarget with coordinates, metadata, and confidence.
        If ambiguous, candidates list is populated and requires_confirmation=True.
        If not found, standard_name is empty and requires_confirmation=True.

    Raises:
        ValueError: If target_name is empty.
    """
    if not target_name or not target_name.strip():
        raise ValueError("target_name cannot be empty")

    catalog = _load_catalog()

    # Score all entries
    scored: list[tuple[float, dict]] = []
    for entry in catalog:
        score = _match_catalog_entry(target_name, entry)
        if score > 0:
            # Apply type filter if provided
            if target_type and entry.get("target_type") != target_type:
                score *= 0.5
            scored.append((score, entry))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Case: no match
    if not scored:
        return ResolvedTarget(
            standard_name="",
            aliases=[],
            target_type="",
            ra_deg=0.0,
            dec_deg=0.0,
            source="built_in_catalog_v1",
            confidence=0.0,
            requires_confirmation=True,
        )

    # Case: single clear match
    # Auto-confirm if best >= 0.9 AND (no competitor OR second < 0.5 OR gap >= 0.08)
    best_score, best_entry = scored[0]
    second_score = scored[1][0] if len(scored) >= 2 else 0.0
    if best_score >= 0.9 and (second_score < 0.5 or (best_score - second_score) >= 0.08):
        return ResolvedTarget(
            standard_name=best_entry["standard_name"],
            aliases=best_entry.get("aliases", []),
            target_type=best_entry["target_type"],
            ra_deg=best_entry["ra_deg"],
            dec_deg=best_entry["dec_deg"],
            visual_magnitude=best_entry.get("visual_magnitude"),
            angular_size_arcmin=best_entry.get("angular_size_arcmin"),
            constellation=best_entry.get("constellation"),
            source="built_in_catalog_v1",
            confidence=best_score,
            requires_confirmation=False,
        )

    # Case: ambiguous — return candidates
    candidates = []
    for score, entry in scored[:10]:  # Top 10 candidates
        candidates.append(
            TargetCandidate(
                standard_name=entry["standard_name"],
                target_type=entry["target_type"],
                ra_deg=entry["ra_deg"],
                dec_deg=entry["dec_deg"],
                source="built_in_catalog_v1",
                confidence=score,
            )
        )

    return ResolvedTarget(
        standard_name=best_entry["standard_name"],
        aliases=best_entry.get("aliases", []),
        target_type=best_entry["target_type"],
        ra_deg=best_entry["ra_deg"],
        dec_deg=best_entry["dec_deg"],
        source="built_in_catalog_v1",
        confidence=best_score,
        candidates=candidates,
        requires_confirmation=True,
    )


def resolve_location(location_key: str) -> Optional[dict]:
    """
    Resolve a location key (e.g. '济南_四门塔') from the built-in table.

    Returns the location dict or None if not found.
    """
    from .config import load_locations

    locations = load_locations()
    for loc in locations:
        if loc.get("key") == location_key:
            return loc
    return None
