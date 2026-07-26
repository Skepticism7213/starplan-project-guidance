"""
StarPlan Loop - SIMBAD TAP Query Script

Reproduces the SIMBAD cross-reference data used for catalog validation.
Referenced by: data/catalog_provenance.json

Usage:
    python scripts/simbad_tap_query.py

Output:
    data/simbad_dim_otype.json — one record per target with:
      standard_name, ra_deg, dec_deg, dim_maj_arcsec, dim_min_arcsec, otype

Requirements:
    - astroquery (`pip install astroquery`)
    - Network access to SIMBAD TAP (http://simbad.cds.unistra.fr/simbad/sim-tap)

Notes:
    - Queries are rate-limited by CDS; full 150-target run takes ~2-3 minutes.
    - Results depend on SIMBAD's current data; coordinates are J2000.0.
    - This script is for reproducibility only; the catalog itself is frozen.
"""

import json
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_PATH = DATA_DIR / "built_in_catalog_v1.json"
OUTPUT_PATH = DATA_DIR / "simbad_dim_otype.json"


def query_simbad():
    """Query SIMBAD for all catalog targets and save results."""
    try:
        from astroquery.simbad import Simbad
    except ImportError:
        print("ERROR: astroquery not installed. Run: pip install astroquery")
        sys.exit(1)

    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    print(f"Catalog: {len(catalog)} targets")
    print(f"Querying SIMBAD TAP (rate-limited, ~2-3 min)...")

    # Configure SIMBAD to return the fields we need
    Simbad.add_votable_fields("dim", "otype")

    results = []
    errors = []

    for i, target in enumerate(catalog):
        name = target["standard_name"]
        try:
            table = Simbad.query_objectids(name)
            if table is None or len(table) == 0:
                # Try first alias
                aliases = target.get("aliases", [])
                if aliases:
                    table = Simbad.query_objectids(aliases[0])

            # Query object data
            obj_table = Simbad.query_object(name)
            if obj_table is None or len(obj_table) == 0:
                if target.get("aliases"):
                    obj_table = Simbad.query_object(target["aliases"][0])

            record = {
                "standard_name": name,
                "ra_deg": None,
                "dec_deg": None,
                "dim_maj_arcsec": None,
                "dim_min_arcsec": None,
                "otype": None,
            }

            if obj_table and len(obj_table) > 0:
                row = obj_table[0]
                # Extract coordinates
                try:
                    from astropy.coordinates import SkyCoord
                    import astropy.units as u
                    ra_str = str(row.get("ra", ""))
                    dec_str = str(row.get("dec", ""))
                    if ra_str and dec_str:
                        coord = SkyCoord(ra_str, dec_str, unit=(u.hourangle, u.deg))
                        record["ra_deg"] = round(float(coord.ra.deg), 5)
                        record["dec_deg"] = round(float(coord.dec.deg), 5)
                except Exception:
                    pass

                # Extract dimensions
                try:
                    dim_maj = row.get("dim_maj_arcsec") or row.get("galdim_maj")
                    dim_min = row.get("dim_min_arcsec") or row.get("galdim_min")
                    if dim_maj is not None:
                        record["dim_maj_arcsec"] = round(float(dim_maj), 2)
                    if dim_min is not None:
                        record["dim_min_arcsec"] = round(float(dim_min), 2)
                except (TypeError, ValueError):
                    pass

                # Extract object type
                try:
                    otype = row.get("otype") or row.get("main_type")
                    if otype:
                        record["otype"] = str(otype).strip()
                except Exception:
                    pass

            results.append(record)

            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(catalog)}")

            # Rate limiting: be gentle with CDS servers
            time.sleep(0.5)

        except Exception as e:
            errors.append({"standard_name": name, "error": str(e)})
            results.append({
                "standard_name": name,
                "ra_deg": None,
                "dec_deg": None,
                "dim_maj_arcsec": None,
                "dim_min_arcsec": None,
                "otype": None,
            })

    # Save results
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Results saved to: {OUTPUT_PATH}")
    print(f"  Successful: {len(results) - len(errors)}/{len(catalog)}")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for e in errors[:5]:
            print(f"    {e['standard_name']}: {e['error'][:80]}")

    return results


if __name__ == "__main__":
    query_simbad()
