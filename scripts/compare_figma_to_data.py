#!/usr/bin/env python3
"""
Plain check: does `figma_raw.json` (your saved Figma file) produce the same wardrobe
data as `data/*.json`?

Run from project root:
  python3 scripts/compare_figma_to_data.py

No API key needed — it only reads local files.
If you update Figma, use File → Save as / export JSON to `figma_raw.json`, or run
`scripts/fetch_figma_file.py` with FIGMA_TOKEN, then run this again.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    spec = importlib.util.spec_from_file_location(
        "extract_figma_wardrobe", ROOT / "scripts" / "extract_figma_wardrobe.py"
    )
    efw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(efw)

    raw = json.loads((ROOT / "figma_raw.json").read_text(encoding="utf-8"))
    pages = {p.get("name"): p for p in raw["document"]["children"]}
    catalog = pages.get("Catalog")
    looks = pages.get("Looks")
    if not catalog or not looks:
        print("figma_raw.json must have Catalog and Looks pages.", file=sys.stderr)
        sys.exit(1)

    comp_to_item, items_f = efw.extract_catalog(catalog)
    clusters_f, matches_f = efw.extract_looks(looks, comp_to_item)

    cur_items = json.loads((ROOT / "data/items.json").read_text())
    cur_clusters = json.loads((ROOT / "data/clusters.json").read_text())
    cur_matches = json.loads((ROOT / "data/top_matches.json").read_text())

    ids_f = {x["item_id"] for x in items_f}
    ids_c = {x["item_id"] for x in cur_items}

    def mk(m):
        return (m["weather_bucket"], m["occasion"], m["source_kind"], m["source_id"])

    keys_f = {mk(m) for m in matches_f}
    keys_c = {mk(m) for m in cur_matches}

    print("What this means:")
    print("  • Catalog page in Figma → item list + #tags (occasions).")
    print("  • Looks page in Figma → which tops go with which bottoms/shoes per weather.")
    print("  • Your app reads data/items.json, clusters.json, top_matches.json.\n")

    print(
        f"Counts: items {len(ids_f)} vs {len(ids_c)} | "
        f"clusters {len(clusters_f)} vs {len(cur_clusters)} | "
        f"looks {len(keys_f)} vs {len(keys_c)}"
    )

    only_f = ids_f - ids_c
    only_c = ids_c - ids_f
    if only_f:
        print(f"\nIDs only in Figma export: {sorted(only_f)}")
    if only_c:
        print(f"\nIDs only in app data (renames or manual): {sorted(only_c)}")

    occ = []
    fi = {x["item_id"]: x for x in items_f}
    ci = {x["item_id"]: x for x in cur_items}
    for iid in set(fi) & set(ci):
        a = sorted(fi[iid].get("occasions", []))
        b = sorted(ci[iid].get("occasions", []))
        if a != b:
            occ.append((iid, a, b))
    if occ:
        print(f"\nOccasion #tags differ ({len(occ)} items) — Figma vs app:")
        for iid, a, b in sorted(occ)[:20]:
            print(f"  {iid}: Figma {a}  |  app {b}")

    mf = {c["cluster_id"]: sorted(c["member_item_ids"]) for c in clusters_f}
    mc = {c["cluster_id"]: sorted(c["member_item_ids"]) for c in cur_clusters}
    for cid in sorted(set(mf) | set(mc)):
        if mf.get(cid) != mc.get(cid):
            print(f"\nCluster {cid} members differ:")
            print(f"  Figma: {mf.get(cid)}")
            print(f"  App:   {mc.get(cid)}")

    mf_map = {mk(m): m for m in matches_f}
    mc_map = {mk(m): m for m in cur_matches}
    slot_diff = 0
    for k in keys_f & keys_c:
        a, b = mf_map[k], mc_map[k]
        for slot in ("bottom_ids", "shoes_ids", "hat_ids", "underlayer_ids", "overlayer_ids"):
            if sorted(a.get(slot) or []) != sorted(b.get(slot) or []):
                slot_diff += 1
                break
    shared = len(keys_f & keys_c)
    print(f"\nLook rows (same weather+occasion+top): {shared} shared.")
    if shared:
        print(f"Of those, {slot_diff} have different bottoms/shoes/hats/layers than a fresh Figma extract.")
        print("(That usually means the app was tuned by hand after export.)")


if __name__ == "__main__":
    main()
