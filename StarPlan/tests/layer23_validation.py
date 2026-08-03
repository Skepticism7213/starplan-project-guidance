"""
Layer 2 & 3: Cross-reference and Semantic Validation (10 rounds)
- Check 5: Coordinate validation (RA/Dec range & internal consistency)
- Check 6: Visual magnitude validation (range per target type)
- Check 7: Angular size vs SIMBAD (requires simbad_dim_otype.json)
- Check 8: NGC number verification
- Check 9: Alias attribution (SIMBAD resolves alias to correct target)
- Check 10: Chinese name verification
- Check 11: Target subtype classification (requires simbad_dim_otype.json)

Note: Checks 7 and 11 require data/simbad_dim_otype.json. If the file is
missing, those checks are skipped with a warning (not treated as failure).
"""
import json
import sys
import math
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.path.insert(0, str(DATA_DIR.parent))
from starplan_skills.encoding import configure_utf8_stdio

configure_utf8_stdio()

# Known correct Chinese names for bright stars (reference)
KNOWN_CHINESE_STAR_NAMES = {
    "Sirius": ["天狼星"],
    "Canopus": ["老人星"],
    "Alpha Centauri": ["南门二", "半人马座α"],
    "Arcturus": ["大角星"],
    "Vega": ["织女星"],
    "Capella": ["五车二"],
    "Rigel": ["参宿七"],
    "Procyon": ["南河三"],
    "Achernar": ["水委一"],
    "Betelgeuse": ["参宿四"],
    "Altair": ["牛郎星", "河鼓二"],
    "Aldebaran": ["毕宿五"],
    "Spica": ["角宿一"],
    "Antares": ["心宿二"],
    "Pollux": ["北河三"],
    "Fomalhaut": ["北落师门"],
    "Deneb": ["天津四"],
    "Regulus": ["轩辕十四"],
    "Castor": ["北河二"],
    "Bellatrix": ["参宿五"],
    "Alnilam": ["参宿二"],
    "Alnitak": ["参宿一"],
    "Alioth": ["玉衡"],
    "Dubhe": ["天枢"],
    "Alkaid": ["摇光"],
    "Polaris": ["北极星", "勾陈一"],
    "Hamal": ["娄宿三"],
    "Saiph": ["参宿六"],
    "Mizar": ["开阳"],
    "Mirach": ["奎宿九"],
    "Alpheratz": ["壁宿二"],
    "Algol": ["大陵五"],
    "Mintaka": ["参宿三"],
    "Denebola": ["五帝座一"],
    "Merak": ["天璇"],
    "Scheat": ["室宿二"],
    "Phecda": ["天玑"],
    "Markab": ["室宿一"],
    "Megrez": ["天权"],
    "Albireo": ["辇道增七"],
}

# Known Messier Chinese names (subset for verification)
KNOWN_MESSIER_CHINESE = {
    "M1": ["蟹状星云"],
    "M6": ["蝴蝶星团"],
    "M8": ["礁湖星云"],
    "M13": ["武仙座球状星团", "大力神星团"],
    "M16": ["鹰状星云"],
    "M17": ["天鹅星云", "欧米伽星云", "奥米伽星云", "马蹄星云"],
    "M20": ["三叶星云", "三裂星云"],
    "M27": ["哑铃星云"],
    "M31": ["仙女座星系", "仙女座大星云"],
    "M33": ["三角座星系"],
    "M42": ["猎户座大星云"],
    "M44": ["蜂巢星团", "鬼星团"],
    "M45": ["昴星团", "七姐妹星团"],
    "M51": ["涡状星系"],
    "M57": ["环状星云"],
    "M63": ["向日葵星系"],
    "M64": ["黑眼星系"],
    "M78": ["奥特曼星云", "猎户座反射星云"],
    "M81": ["波德星系"],
    "M82": ["雪茄星系"],
    "M97": ["猫头鹰星云"],
    "M101": ["风车星系"],
    "M104": ["草帽星系"],
    "M110": ["仙女座伴星系"],
}

# SIMBAD object types that are "star-like" (should be target_type=star)
STAR_OTYPES = {
    "Star", "V*", "gD*", "HB*", "RG*", "WR*", "Be*", "Ae*",
    "Em*", "BS*", "PM*", "Pec*", "Er*", "Or*", "Fl*", "BY*",
    "RS*", "TT*", "T*", "WD*", "BD*", "N*", "Pu*", "SN*",
    "LM*", "HV*", "s*r", "s*b", "s*y", "s*g", "s*r",
    "**", "EB*", "Al*", "El*", "SB*", "C*", "S*",
}

# SIMBAD object types that are "deep sky" (should be target_type=deep_sky)
DEEP_SKY_OTYPES = {
    "G", "GPa", "GiG", "GiP", "GCl", "G?", "EmG", "SBG",
    "AGN", "QSO", "LIN", "Sy1", "Sy2", "SyG",
    "Cl*", "GlC", "OpC", "St*", "As*",
    "HII", "PN", "RfN", "DkN", "MoC", "Cld",
    "SNR", "Nova", "out", "reg",
    "Ne", "Neb",
}


def load_data():
    with open(DATA_DIR / "built_in_catalog_v1.json", encoding="utf-8") as f:
        catalog = json.load(f)

    simbad_path = DATA_DIR / "simbad_dim_otype.json"
    simbad_map = {}
    if simbad_path.exists():
        with open(simbad_path, encoding="utf-8") as f:
            simbad = json.load(f)
        simbad_map = {r["standard_name"]: r for r in simbad}
    else:
        print(f"  [WARN] {simbad_path.name} not found — "
              f"SIMBAD cross-reference checks (7, 11) will be skipped.")

    return catalog, simbad_map


def check_provenance(catalog, simbad_map, round_num):
    """Check 4: Catalog data provenance/traceability metadata."""
    issues = []
    prov_path = DATA_DIR / "catalog_provenance.json"

    if not prov_path.exists():
        issues.append(
            "CRITICAL | catalog_provenance.json missing — "
            "no data source traceability"
        )
        return issues

    with open(prov_path, encoding="utf-8") as f:
        prov = json.load(f)

    # Required top-level fields
    required_fields = ["field_sources", "simbad_query_info", "validation_history"]
    for field in required_fields:
        if field not in prov:
            issues.append(f"CRITICAL | provenance missing required field: {field}")

    # Check field_sources covers all catalog fields
    catalog_fields = {"ra_deg", "dec_deg", "visual_magnitude", "angular_size_arcmin",
                      "constellation", "aliases", "target_type", "standard_name"}
    documented = set(prov.get("field_sources", {}).keys())
    missing_docs = catalog_fields - documented
    if missing_docs:
        issues.append(
            f"WARNING | provenance field_sources missing docs for: {missing_docs}"
        )

    # Check simbad_query_info has query_date
    sqi = prov.get("simbad_query_info", {})
    if not sqi.get("query_date"):
        issues.append("WARNING | simbad_query_info missing query_date")

    return issues


def check_coordinates(catalog, simbad_map, round_num):
    """Check 5: Coordinate validation (RA/Dec range & internal consistency)."""
    issues = []
    seen_coords = {}  # (ra_rounded, dec_rounded) -> target_name

    for t in catalog:
        name = t["standard_name"]
        ra = t.get("ra_deg")
        dec = t.get("dec_deg")

        # Check RA range [0, 360)
        if ra is None:
            issues.append(f"CRITICAL | {name} | missing ra_deg")
        elif ra < 0 or ra >= 360:
            issues.append(f"CRITICAL | {name} | ra_deg={ra} out of range [0, 360)")

        # Check Dec range [-90, 90]
        if dec is None:
            issues.append(f"CRITICAL | {name} | missing dec_deg")
        elif dec < -90 or dec > 90:
            issues.append(f"CRITICAL | {name} | dec_deg={dec} out of range [-90, 90]")

        if ra is None or dec is None:
            continue

        # Check for duplicate coordinates (within 0.01 degree ~ 36 arcsec)
        coord_key = (round(ra, 2), round(dec, 2))
        if coord_key in seen_coords:
            other = seen_coords[coord_key]
            issues.append(
                f"WARNING | {name} | coordinates nearly identical to {other} "
                f"(RA={ra:.4f}, Dec={dec:.4f})"
            )
        else:
            seen_coords[coord_key] = name

        # On odd rounds: check RA/Dec precision (should have >= 2 decimal places)
        # Note: some objects genuinely sit at exact sexagesimal boundaries
        # (e.g. M24 RA=274.2 = exactly 18h16m48s), so we require >= 2 not >= 3.
        # P2-2 fix: allowlist for targets at exact sexagesimal boundaries —
        # their coordinates ARE the exact conversion and cannot gain precision.
        EXACT_SEXAGESIMAL_BOUNDARY = {"M24", "M52"}
        if round_num % 2 == 1 and name not in EXACT_SEXAGESIMAL_BOUNDARY:
            ra_str = str(ra)
            dec_str = str(dec)
            if "." in ra_str and len(ra_str.split(".")[1]) < 2:
                issues.append(
                    f"WARNING | {name} | ra_deg={ra} has low precision "
                    f"(< 2 decimal places)"
                )
            if "." in dec_str and len(dec_str.split(".")[1]) < 2:
                issues.append(
                    f"WARNING | {name} | dec_deg={dec} has low precision "
                    f"(< 2 decimal places)"
                )

    return issues


def check_visual_magnitude(catalog, simbad_map, round_num):
    """Check 6: Visual magnitude validation (range per target type)."""
    issues = []

    for t in catalog:
        name = t["standard_name"]
        mag = t.get("visual_magnitude")
        ttype = t.get("target_type", "")

        if mag is None:
            # Missing magnitude is a warning, not critical
            issues.append(f"WARNING | {name} | missing visual_magnitude")
            continue

        # Range checks per target type
        if ttype == "star":
            # Bright stars catalog: should be roughly -2 to +7
            if mag < -2.0 or mag > 7.0:
                issues.append(
                    f"CRITICAL | {name} | star magnitude {mag} "
                    f"outside expected range [-2, 7]"
                )
        elif ttype == "deep_sky":
            # Messier objects: roughly +1.5 to +11
            if mag < -1.0 or mag > 12.0:
                issues.append(
                    f"CRITICAL | {name} | deep_sky magnitude {mag} "
                    f"outside expected range [-1, 12]"
                )

        # On even rounds: check for magnitude precision (should have 1 decimal)
        if round_num % 2 == 0:
            mag_str = str(mag)
            if "." in mag_str and len(mag_str.split(".")[1]) > 2:
                issues.append(
                    f"WARNING | {name} | magnitude {mag} has unusual precision"
                )

    return issues


def check_angular_size(catalog, simbad_map, round_num):
    """Check 7: Angular size comparison with SIMBAD."""
    issues = []
    # Tolerance varies by round: 20% on even, 30% on odd
    tolerance = 0.20 if round_num % 2 == 0 else 0.30

    for t in catalog:
        name = t["standard_name"]
        json_size = t.get("angular_size_arcmin")
        s = simbad_map.get(name)
        if not s:
            continue

        simbad_maj = s.get("dim_maj_arcsec")
        simbad_min = s.get("dim_min_arcsec")

        if json_size is None:
            continue  # Already checked in Layer 1

        if simbad_maj is None or simbad_maj == 0:
            continue  # SIMBAD doesn't have size data

        # Convert SIMBAD arcsec to arcmin
        simbad_maj_arcmin = simbad_maj / 60.0
        simbad_min_arcmin = (simbad_min / 60.0) if simbad_min else simbad_maj_arcmin

        json_maj = max(json_size)
        json_min = min(json_size)

        # Compare major axis
        if simbad_maj_arcmin > 0:
            ratio = json_maj / simbad_maj_arcmin
            if ratio > (1 + tolerance) or ratio < (1 - tolerance):
                issues.append(
                    f"WARNING | {name} | angular_size major axis: "
                    f"JSON={json_maj:.1f}' vs SIMBAD={simbad_maj_arcmin:.1f}' "
                    f"(ratio={ratio:.2f}, tolerance={tolerance:.0%})"
                )

    return issues


def check_ngc_numbers(catalog, simbad_map, round_num):
    """Check 8: Verify NGC numbers in aliases resolve to correct target."""
    issues = []

    # Build expected NGC->Messier mapping from SIMBAD main_id
    # We check internal consistency: no two targets share an NGC number
    ngc_to_targets = defaultdict(list)
    for t in catalog:
        for alias in t.get("aliases", []):
            if alias.upper().startswith("NGC"):
                ngc_num = alias.upper().replace("NGC", "").strip()
                ngc_to_targets[ngc_num].append(t["standard_name"])

    for ngc, targets in ngc_to_targets.items():
        if len(targets) > 1:
            issues.append(
                f"CRITICAL | NGC {ngc} claimed by multiple targets: {targets}"
            )

    # On odd rounds, verify NGC format is valid (numeric)
    if round_num % 2 == 1:
        for t in catalog:
            for alias in t.get("aliases", []):
                if alias.upper().startswith("NGC"):
                    num_part = alias.upper().replace("NGC", "").strip()
                    if not num_part.isdigit():
                        issues.append(
                            f"CRITICAL | {t['standard_name']} | "
                            f"invalid NGC format: '{alias}'"
                        )

    # On rounds divisible by 3, check that Messier objects with known NGC
    # numbers have them in aliases
    if round_num % 3 == 0:
        # Well-known M->NGC that MUST be present
        required_ngc = {
            "M1": "1952", "M31": "224", "M42": "1976", "M45": None,  # M45 has no NGC
            "M13": "6205", "M51": "5194", "M57": "6720",
            "M27": "6853", "M97": "3587", "M101": "5457",
            "M104": "4594", "M81": "3031", "M82": "3034",
        }
        for m_name, ngc_num in required_ngc.items():
            if ngc_num is None:
                continue
            entry = next((t for t in catalog if t["standard_name"] == m_name), None)
            if entry:
                aliases_upper = [a.upper() for a in entry.get("aliases", [])]
                expected = f"NGC {ngc_num}"
                if expected not in aliases_upper:
                    issues.append(
                        f"WARNING | {m_name} | expected alias '{expected}' not found "
                        f"in {entry['aliases']}"
                    )

    return issues


def check_alias_attribution(catalog, simbad_map, round_num):
    """Check 9: Verify aliases are plausible for the target."""
    issues = []

    for t in catalog:
        name = t["standard_name"]
        aliases = t.get("aliases", [])

        # Check: aliases should not be empty
        if not aliases:
            issues.append(f"WARNING | {name} | no aliases")
            continue

        # Check: no alias should be identical to another target's standard_name
        all_std_names = {e["standard_name"].lower() for e in catalog}
        for alias in aliases:
            if alias.lower() in all_std_names and alias.lower() != name.lower():
                issues.append(
                    f"CRITICAL | {name} | alias '{alias}' is another target's name"
                )

        # Check: NGC aliases should be unique across catalog
        # (already done in check 8, skip on even rounds to vary)
        if round_num % 2 == 1:
            # Check English aliases don't contain obvious wrong constellation references
            constellation = t.get("constellation", "")
            for alias in aliases:
                # If alias contains a constellation name different from target's
                for other_const in ["Orion", "Cygnus", "Lyra", "Aquila",
                                    "Ursa Major", "Scorpius", "Sagittarius",
                                    "Andromeda", "Perseus", "Cassiopeia"]:
                    if (other_const in alias and
                        other_const != constellation and
                        constellation not in alias):
                        # Only flag if it's clearly a descriptive name mismatch
                        if "Cluster" in alias or "Nebula" in alias or "Galaxy" in alias:
                            issues.append(
                                f"WARNING | {name} ({constellation}) | "
                                f"alias '{alias}' references different constellation"
                            )

    return issues


def check_chinese_names(catalog, simbad_map, round_num):
    """Check 10: Verify Chinese names against known references."""
    issues = []

    for t in catalog:
        name = t["standard_name"]
        aliases = t.get("aliases", [])
        chinese_aliases = [a for a in aliases if any('\u4e00' <= c <= '\u9fff' for c in a)]

        if t["target_type"] == "star":
            # Check against known star Chinese names
            if name in KNOWN_CHINESE_STAR_NAMES:
                expected_names = KNOWN_CHINESE_STAR_NAMES[name]
                found = any(
                    any(exp in ca for exp in expected_names)
                    for ca in chinese_aliases
                )
                if not found and chinese_aliases:
                    # Has Chinese aliases but none match known names
                    issues.append(
                        f"WARNING | {name} | Chinese aliases {chinese_aliases} "
                        f"don't match known names {expected_names}"
                    )
                elif not chinese_aliases:
                    issues.append(
                        f"WARNING | {name} | no Chinese alias "
                        f"(expected one of {expected_names})"
                    )

        elif t["target_type"] == "deep_sky":
            # Check against known Messier Chinese names
            if name in KNOWN_MESSIER_CHINESE:
                expected_names = KNOWN_MESSIER_CHINESE[name]
                found = any(
                    any(exp in ca for exp in expected_names)
                    for ca in chinese_aliases
                )
                if not found and chinese_aliases:
                    issues.append(
                        f"WARNING | {name} | Chinese aliases {chinese_aliases} "
                        f"don't match known names {expected_names}"
                    )

        # On odd rounds: check that Chinese aliases contain the constellation
        # name in Chinese (for descriptive names like "XX座YY")
        if round_num % 2 == 1 and t["target_type"] == "deep_sky":
            constellation = t.get("constellation", "")
            # Common Chinese constellation suffixes
            for ca in chinese_aliases:
                if "座" in ca and constellation:
                    # Extract the constellation part before 座
                    pass  # Too complex for automated check, skip

    return issues


def check_target_subtype(catalog, simbad_map, round_num):
    """Check 11: Verify target_type against SIMBAD object type."""
    issues = []

    for t in catalog:
        name = t["standard_name"]
        json_type = t["target_type"]
        s = simbad_map.get(name)
        if not s or not s.get("otype"):
            continue

        otype = s["otype"].strip()

        # Check if star is classified as deep_sky or vice versa
        is_star_otype = otype in STAR_OTYPES or otype.startswith("*") or otype.startswith("V")
        is_ds_otype = otype in DEEP_SKY_OTYPES or otype.startswith("G") or otype.startswith("Cl")

        if json_type == "star" and is_ds_otype and not is_star_otype:
            issues.append(
                f"CRITICAL | {name} | JSON says 'star' but SIMBAD otype='{otype}' "
                f"(deep sky object)"
            )
        elif json_type == "deep_sky" and is_star_otype and not is_ds_otype:
            # Some Messier objects are double stars (M40) or asterisms
            # Only flag if it's clearly a single star
            if otype in ("Star", "V*", "PM*", "WD*", "BD*"):
                issues.append(
                    f"WARNING | {name} | JSON says 'deep_sky' but SIMBAD "
                    f"otype='{otype}' (single star)"
                )

        # On rounds divisible by 3, also check for galaxies labeled wrong
        if round_num % 3 == 0:
            if json_type == "star" and otype.startswith("G"):
                issues.append(
                    f"CRITICAL | {name} | JSON says 'star' but SIMBAD "
                    f"otype='{otype}' (galaxy!)"
                )

    return issues


def main():
    catalog, simbad_map = load_data()
    print(f"Catalog: {len(catalog)} targets, SIMBAD data: {len(simbad_map)} entries")
    print(f"Running 10 rounds of Layer 2+3 validation...\n")

    all_issues = defaultdict(set)
    round_summaries = []

    checks = [
        ("Provenance", check_provenance),
        ("Coordinate", check_coordinates),
        ("VisualMagnitude", check_visual_magnitude),
        ("AngularSize", check_angular_size),
        ("NGC-Number", check_ngc_numbers),
        ("Alias-Attribution", check_alias_attribution),
        ("Chinese-Name", check_chinese_names),
        ("Target-Subtype", check_target_subtype),
    ]

    for round_num in range(1, 11):
        round_issues = []
        for check_name, check_fn in checks:
            issues = check_fn(catalog, simbad_map, round_num)
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
