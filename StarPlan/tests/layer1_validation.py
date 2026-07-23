"""
Layer 1: Internal Consistency Validation (10 rounds)
Checks: range, constellation boundary, type-attribute, alias conflicts.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astropy.coordinates import SkyCoord, get_constellation
import astropy.units as u

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "built_in_catalog_v1.json"

# Valid IAU constellation abbreviations -> full names mapping
IAU_CONSTELLATIONS = {
    "Andromeda", "Antlia", "Apus", "Aquarius", "Aquila", "Ara",
    "Aries", "Auriga", "Bootes", "Caelum", "Camelopardalis", "Cancer",
    "Canes Venatici", "Canis Major", "Canis Minor", "Capricornus",
    "Carina", "Cassiopeia", "Centaurus", "Cepheus", "Cetus",
    "Chamaeleon", "Circinus", "Columba", "Coma Berenices",
    "Corona Australis", "Corona Borealis", "Corvus", "Crater",
    "Crux", "Cygnus", "Delphinus", "Dorado", "Draco", "Equuleus",
    "Eridanus", "Fornax", "Gemini", "Grus", "Hercules", "Horologium",
    "Hydra", "Hydrus", "Indus", "Lacerta", "Leo", "Leo Minor",
    "Lepus", "Libra", "Lupus", "Lynx", "Lyra", "Mensa",
    "Microscopium", "Monoceros", "Musca", "Norma", "Octans",
    "Ophiuchus", "Orion", "Pavo", "Pegasus", "Perseus", "Phoenix",
    "Pictor", "Pisces", "Piscis Austrinus", "Puppis", "Pyxis",
    "Reticulum", "Sagitta", "Sagittarius", "Scorpius", "Sculptor",
    "Scutum", "Serpens", "Sextans", "Taurus", "Telescopium",
    "Triangulum", "Triangulum Australe", "Tucana", "Ursa Major",
    "Ursa Minor", "Vela", "Virgo", "Volans", "Vulpecula",
}


def load_catalog():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_ranges(catalog, round_num):
    """Check 1: Numerical range validation with varying strictness."""
    issues = []
    # Tighter bounds on odd rounds
    mag_star_lo = -2.0 if round_num % 2 == 0 else -1.5
    mag_star_hi = 7.0 if round_num % 2 == 0 else 6.5
    mag_ds_lo = 0.0 if round_num % 2 == 0 else 1.0
    mag_ds_hi = 12.0 if round_num % 2 == 0 else 11.5
    size_max = 600 if round_num % 2 == 0 else 400

    for t in catalog:
        name = t["standard_name"]
        ra, dec = t["ra_deg"], t["dec_deg"]

        if ra < 0 or ra >= 360:
            issues.append(f"CRITICAL | {name} | ra_deg={ra} out of [0,360)")
        if dec < -90 or dec > 90:
            issues.append(f"CRITICAL | {name} | dec_deg={dec} out of [-90,+90]")

        mag = t["visual_magnitude"]
        if mag is None:
            issues.append(f"WARNING | {name} | visual_magnitude is None")
        elif t["target_type"] == "star" and (mag < mag_star_lo or mag > mag_star_hi):
            issues.append(f"WARNING | {name} | star mag={mag} outside [{mag_star_lo},{mag_star_hi}]")
        elif t["target_type"] == "deep_sky" and (mag < mag_ds_lo or mag > mag_ds_hi):
            issues.append(f"WARNING | {name} | deep_sky mag={mag} outside [{mag_ds_lo},{mag_ds_hi}]")

        size = t.get("angular_size_arcmin")
        if size is not None:
            if not isinstance(size, list) or len(size) != 2:
                issues.append(f"CRITICAL | {name} | angular_size format invalid: {size}")
            elif size[0] <= 0 or size[1] <= 0:
                issues.append(f"CRITICAL | {name} | angular_size non-positive: {size}")
            elif size[0] > size_max or size[1] > size_max:
                issues.append(f"WARNING | {name} | angular_size > {size_max}: {size}")

        if t["target_type"] not in ("deep_sky", "star"):
            issues.append(f"CRITICAL | {name} | invalid target_type: {t['target_type']}")
        if not t.get("constellation"):
            issues.append(f"CRITICAL | {name} | constellation missing")
        if not t.get("aliases") or len(t["aliases"]) == 0:
            issues.append(f"WARNING | {name} | aliases empty")

    return issues


def check_constellation_boundary(catalog, round_num):
    """Check 2: Verify RA/Dec falls within stated constellation (IAU boundaries)."""
    issues = []
    for t in catalog:
        name = t["standard_name"]
        coord = SkyCoord(ra=t["ra_deg"] * u.deg, dec=t["dec_deg"] * u.deg, frame="icrs")
        actual_const = get_constellation(coord)
        stated = t["constellation"]

        if actual_const != stated:
            issues.append(
                f"CRITICAL | {name} | stated constellation '{stated}' "
                f"but coords ({t['ra_deg']:.4f}, {t['dec_deg']:.4f}) "
                f"fall in '{actual_const}'"
            )
    return issues


def check_type_attribute(catalog, round_num):
    """Check 3: Type-attribute consistency."""
    issues = []
    for t in catalog:
        name = t["standard_name"]
        ttype = t["target_type"]
        size = t.get("angular_size_arcmin")

        # Stars should NOT have angular_size (point sources)
        if ttype == "star" and size is not None:
            issues.append(
                f"WARNING | {name} | star has angular_size_arcmin={size} "
                f"(stars are point sources)"
            )

        # Deep sky objects SHOULD have angular_size
        if ttype == "deep_sky" and size is None:
            issues.append(
                f"WARNING | {name} | deep_sky missing angular_size_arcmin"
            )

        # Deep sky: check size plausibility by magnitude
        if ttype == "deep_sky" and size is not None:
            mag = t["visual_magnitude"]
            max_dim = max(size)
            # Very bright objects (mag < 4) should be large (> 10 arcmin)
            if round_num % 3 == 0 and mag is not None and mag < 4.0 and max_dim < 5:
                issues.append(
                    f"INFO | {name} | bright deep_sky (mag={mag}) but small "
                    f"angular_size={size} - verify"
                )
            # Very faint objects (mag > 10) shouldn't be huge (> 30 arcmin)
            if round_num % 3 == 1 and mag is not None and mag > 10.0 and max_dim > 30:
                issues.append(
                    f"INFO | {name} | faint deep_sky (mag={mag}) but large "
                    f"angular_size={size} - verify"
                )

    return issues


def check_alias_conflicts(catalog, round_num):
    """Check 4: Alias uniqueness and NGC number conflicts."""
    issues = []

    # Build alias -> target map
    alias_map = defaultdict(list)
    ngc_map = defaultdict(list)

    for t in catalog:
        name = t["standard_name"]
        for alias in t.get("aliases", []):
            alias_lower = alias.lower().strip()
            alias_map[alias_lower].append(name)
            if alias.upper().startswith("NGC"):
                ngc_num = alias.upper().replace("NGC", "").strip()
                ngc_map[ngc_num].append(name)

    # Check for duplicate aliases (same alias pointing to multiple targets)
    for alias, targets in alias_map.items():
        if len(targets) > 1:
            issues.append(
                f"CRITICAL | alias '{alias}' claimed by multiple targets: {targets}"
            )

    # Check for duplicate NGC numbers
    for ngc, targets in ngc_map.items():
        if len(targets) > 1:
            issues.append(
                f"CRITICAL | NGC {ngc} claimed by multiple targets: {targets}"
            )

    # Check standard_name not appearing in another target's aliases
    all_names = {t["standard_name"].lower() for t in catalog}
    for t in catalog:
        for alias in t.get("aliases", []):
            if alias.lower() in all_names and alias.lower() != t["standard_name"].lower():
                issues.append(
                    f"WARNING | {t['standard_name']} has alias '{alias}' "
                    f"which is another target's standard_name"
                )

    # On odd rounds, also check that aliases don't contain the target's own name
    if round_num % 2 == 1:
        for t in catalog:
            name_lower = t["standard_name"].lower()
            for alias in t.get("aliases", []):
                if alias.lower() == name_lower:
                    issues.append(
                        f"INFO | {t['standard_name']} | alias duplicates standard_name"
                    )

    return issues


def main():
    catalog = load_catalog()
    print(f"Catalog loaded: {len(catalog)} targets")
    print(f"Running 10 rounds of Layer 1 validation...\n")

    all_issues = defaultdict(set)  # deduplicate across rounds
    round_summaries = []

    checks = [
        ("Range", check_ranges),
        ("Constellation", check_constellation_boundary),
        ("Type-Attribute", check_type_attribute),
        ("Alias-Conflict", check_alias_conflicts),
    ]

    for round_num in range(1, 11):
        round_issues = []
        for check_name, check_fn in checks:
            issues = check_fn(catalog, round_num)
            for issue in issues:
                all_issues[check_name].add(issue)
            round_issues.extend(issues)
        round_summaries.append(len(round_issues))
        print(f"  Round {round_num:2d}: {len(round_issues)} issues found")

    # Final report
    print(f"\n{'='*60}")
    print(f"FINAL REPORT (deduplicated across 10 rounds)")
    print(f"{'='*60}")

    total_unique = 0
    for check_name, _ in checks:
        issues = sorted(all_issues[check_name])
        total_unique += len(issues)
        print(f"\n--- {check_name} ({len(issues)} unique issues) ---")
        if issues:
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  [ALL PASS]")

    print(f"\n{'='*60}")
    print(f"TOTAL UNIQUE ISSUES: {total_unique}")
    print(f"Round consistency: {round_summaries}")
    print(f"{'='*60}")

    return total_unique


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
