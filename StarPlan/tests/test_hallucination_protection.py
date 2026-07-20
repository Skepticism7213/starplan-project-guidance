"""
StarPlan Loop - Hallucination Protection Tests (Week 3)

Tests that the validation layer in outreach_pack correctly:
  1. Accepts talking points whose numbers all trace to fact cards
  2. Rejects talking points containing fabricated numbers
  3. Handles edge cases (no numbers, Chinese numerals, etc.)

These tests do NOT require a Qwen API key — they test the validation
logic directly. Integration tests with actual Qwen calls are in
test_qwen_integration.py.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.schemas import FactCard
from starplan_skills.outreach_pack import _validate_talking_points


# ── Test fixtures ────────────────────────────────────

def _make_m31_fact_cards() -> list[FactCard]:
    """Fact cards matching M31 (Andromeda Galaxy) observation."""
    return [
        FactCard(key="standard_name", value="M31", source="built_in_catalog_v1"),
        FactCard(key="target_type", value="deep_sky", source="built_in_catalog_v1"),
        FactCard(key="coordinates", value="RA=10.6847°, Dec=41.2689°", source="built_in_catalog_v1"),
        FactCard(key="visual_magnitude", value="3.4", source="built_in_catalog_v1"),
        FactCard(key="angular_size", value="178.0' × 63.0'", source="built_in_catalog_v1"),
        FactCard(key="constellation", value="Andromeda", source="built_in_catalog_v1"),
        FactCard(key="peak_altitude", value="72.3°", source="astroplan/astropy"),
    ]


def _make_vega_fact_cards() -> list[FactCard]:
    """Fact cards matching Vega observation."""
    return [
        FactCard(key="standard_name", value="Vega", source="built_in_catalog_v1"),
        FactCard(key="target_type", value="star", source="built_in_catalog_v1"),
        FactCard(key="coordinates", value="RA=279.2347°, Dec=38.7837°", source="built_in_catalog_v1"),
        FactCard(key="visual_magnitude", value="0.0", source="built_in_catalog_v1"),
        FactCard(key="constellation", value="Lyra", source="built_in_catalog_v1"),
        FactCard(key="peak_altitude", value="85.1°", source="astroplan/astropy"),
    ]


# ── Unit tests: _validate_talking_points ─────────────

def test_valid_points_pass():
    """Talking points with only fact-card numbers should pass."""
    cards = _make_m31_fact_cards()
    points = [
        "今晚我们要观测的是 M31，也就是仙女座星系",
        "它的视星等约为 3.4，在黑暗环境下肉眼可见",
        "它在天空中的角大小约为 178.0 角分，相当于 6 个满月",
        "今晚它的峰值高度角将达到 72.3°，非常适合观测",
        "它位于 Andromeda 星座方向",
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == len(points), f"Expected all points to pass, got issues: {issues}"
    assert len(issues) == 0


def test_hallucinated_number_rejected():
    """A talking point with a fabricated number should be rejected."""
    cards = _make_m31_fact_cards()
    points = [
        "M31 距离地球约 254 万光年",  # 254 not in fact cards
        "它的视星等约为 3.4",  # valid
        "它的直径约为 22 万光年",  # 22 not in fact cards
    ]
    validated, issues = _validate_talking_points(points, cards)
    # "254" and "22" are not in fact cards (beyond safe single digits)
    assert len(issues) >= 1, "Should have flagged hallucinated numbers"
    # The valid point should still pass
    assert "它的视星等约为 3.4" in validated


def test_no_numbers_always_passes():
    """Talking points without any numbers should always pass."""
    cards = _make_m31_fact_cards()
    points = [
        "仙女座星系是离我们最近的大型旋涡星系",
        "使用双筒望远镜可以看到一团模糊的光斑",
        "建议大家先用肉眼熟悉星空，找到目标所在的大致方向",
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == 3
    assert len(issues) == 0


def test_safe_small_numbers_pass():
    """Single-digit numbers (1-10) are considered safe and should pass."""
    cards = _make_m31_fact_cards()
    points = [
        "使用星桥法：从已知的 2 颗亮星出发，逐步找到目标",
        "大约需要 5 分钟适应黑暗",
        "每组 3 人共享一台望远镜",
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == 3, f"Small numbers should be safe, got issues: {issues}"


def test_coordinate_numbers_pass():
    """Numbers from coordinate strings in fact cards should be allowed."""
    cards = _make_m31_fact_cards()
    points = [
        "它的赤经约为 10.6847 度",
        "赤纬约为 41.2689 度",
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == 2, f"Coordinate numbers should pass, got issues: {issues}"


def test_mixed_valid_and_invalid():
    """Only invalid points are removed; valid ones are kept."""
    cards = _make_vega_fact_cards()
    points = [
        "织女星（Vega）是天琴座最亮的恒星",  # no numbers, pass
        "它的视星等为 0.0，是北半球最亮的恒星之一",  # 0.0 in cards, pass
        "它距离地球约 25 光年",  # 25 not in cards, reject
        "今晚峰值高度角将达到 85.1°",  # 85.1 in cards, pass
        "它的表面温度约为 9600 开尔文",  # 9600 not in cards, reject
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == 3
    assert len(issues) == 2
    assert "织女星（Vega）是天琴座最亮的恒星" in validated
    assert "今晚峰值高度角将达到 85.1°" in validated


def test_empty_input():
    """Empty talking points list should return empty results."""
    cards = _make_m31_fact_cards()
    validated, issues = _validate_talking_points([], cards)
    assert validated == []
    assert issues == []


def test_empty_fact_cards():
    """With no fact cards, only number-free points should pass."""
    cards = []
    points = [
        "仙女座星系很美丽",  # no numbers, pass
        "它距离我们 254 万光年",  # has number, no cards to verify, reject
    ]
    validated, issues = _validate_talking_points(points, cards)
    assert len(validated) == 1
    assert len(issues) == 1


# ── Run all tests ────────────────────────────────────

def run_all():
    """Run all hallucination protection tests."""
    tests = [
        test_valid_points_pass,
        test_hallucinated_number_rejected,
        test_no_numbers_always_passes,
        test_safe_small_numbers_pass,
        test_coordinate_numbers_pass,
        test_mixed_valid_and_invalid,
        test_empty_input,
        test_empty_fact_cards,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test_fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {passed + failed} total")
    return failed == 0


if __name__ == "__main__":
    print("=" * 60)
    print("StarPlan Hallucination Protection Tests")
    print("=" * 60)
    success = run_all()
    sys.exit(0 if success else 1)
