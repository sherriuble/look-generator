import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "figma_raw.json"
OUT_DIR = ROOT / "data"


CATEGORY_TO_TYPE = {
    "t-shirts": ("top", "tshirt"),
    "shirts": ("top", "shirt"),
    "hoodies, sweatshirts, sweaters": ("top", "hoodie_sweater"),
    "longsleeves": ("top", "longsleeve"),
    "dresses": ("top", "dress"),
    "shorts": ("bottom", "shorts"),
    "pants": ("bottom", "pants"),
    "hats": ("hat", "hat"),
    "shoes": ("shoes", "shoes"),
    "jackets, coats, blazers": ("overlayer", "jacket_coat_blazer"),
}

WEATHER_MAP = {
    "Hot, Warm": "hot_warm",
    "Pleasant, Chilly": "pleasant_chilly",
    "Cold": "cold",
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def walk(node):
    yield node
    for child in node.get("children", []) or []:
        yield from walk(child)


def text_nodes(node):
    return [n.get("characters", "") for n in walk(node) if n.get("type") == "TEXT" and n.get("characters")]


def parse_mode_item(component_name: str):
    mode = None
    item = None
    for part in component_name.split(","):
        part = part.strip()
        if part.startswith("Mode="):
            mode = part.replace("Mode=", "").strip()
        if part.startswith("Item="):
            item = part.replace("Item=", "").strip()
    return mode, item


def parse_tags_from_texts(texts):
    tags = []
    for t in texts:
        if "#" in t:
            tags.extend(re.findall(r"#([A-Za-z0-9_/-]+)", t))
    clean = []
    for t in tags:
        v = slugify(t)
        if v and v not in clean:
            clean.append(v)
    return clean


def weather_from_frame_name(name: str):
    return WEATHER_MAP.get(name)


def split_occasions(text: str):
    raw = text.lower().replace("&", "/")
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    out = []
    for p in parts:
        s = slugify(p)
        if s in {"casual", "sport", "work", "nice"} and s not in out:
            out.append(s)
    return out or ["casual"]


def extract_catalog(catalog_page):
    item_by_component_id = {}
    item_by_id = {}

    for section in catalog_page.get("children", []):
        if section.get("type") != "COMPONENT_SET":
            continue

        section_key = section.get("name", "").strip().lower()
        if section_key not in CATEGORY_TO_TYPE:
            continue
        item_type, subtype = CATEGORY_TO_TYPE[section_key]

        for component in section.get("children", []):
            if component.get("type") != "COMPONENT":
                continue

            mode, item_name = parse_mode_item(component.get("name", ""))
            texts = text_nodes(component)
            tags = parse_tags_from_texts(texts)

            label_from_text = next((t for t in texts if "#" not in t), None)
            canonical_name = (item_name or label_from_text or component.get("name", "Unnamed")).strip()
            item_id = f"{item_type}_{subtype}_{slugify(canonical_name)}"

            existing = item_by_id.get(item_id)
            if not existing:
                item_by_id[item_id] = {
                    "item_id": item_id,
                    "name": canonical_name,
                    "type": item_type,
                    "subtype": subtype,
                    "occasions": [],
                    "weather_buckets": ["hot_warm", "pleasant_chilly", "cold"],
                    "figma_component_ids": [],
                    "active": True,
                }
                existing = item_by_id[item_id]

            for tg in tags:
                if tg in {"sport", "casual", "work", "nice"} and tg not in existing["occasions"]:
                    existing["occasions"].append(tg)
            if not existing["occasions"]:
                existing["occasions"] = ["casual"]

            comp_id = component.get("id")
            if comp_id:
                item_by_component_id[comp_id] = item_id
                if comp_id not in existing["figma_component_ids"]:
                    existing["figma_component_ids"].append(comp_id)

            if mode:
                existing.setdefault("figma_modes", [])
                smode = slugify(mode)
                if smode not in existing["figma_modes"]:
                    existing["figma_modes"].append(smode)

    return item_by_component_id, list(item_by_id.values())


def collect_instance_item_ids(node, component_to_item):
    ids = []
    for n in walk(node):
        if n.get("type") == "INSTANCE":
            comp_id = n.get("componentId")
            item_id = component_to_item.get(comp_id)
            if item_id and item_id not in ids:
                ids.append(item_id)
    return ids


def find_child_by_name(node, name):
    for ch in node.get("children", []) or []:
        if ch.get("name") == name:
            return ch
    return None


def extract_looks(looks_page, component_to_item):
    top_matches = []
    clusters = {}
    cluster_seq = 1

    for weather_frame in looks_page.get("children", []):
        weather_bucket = weather_from_frame_name(weather_frame.get("name", ""))
        if not weather_bucket:
            continue

        main = find_child_by_name(weather_frame, "Main Frame")
        if not main:
            continue

        for occasion_block in main.get("children", []):
            if occasion_block.get("type") != "FRAME":
                continue

            title_node = find_child_by_name(occasion_block, "Category Title")
            if not title_node or title_node.get("type") != "TEXT":
                continue
            occasions = split_occasions(title_node.get("characters", "casual"))

            main_container = find_child_by_name(occasion_block, "Main Container")
            if not main_container:
                continue

            product_list = find_child_by_name(main_container, "Product List")
            if not product_list:
                continue

            top_entries = []
            for top_candidate in product_list.get("children", []):
                members = collect_instance_item_ids(top_candidate, component_to_item)
                if members:
                    top_entries.append(members)

            if not top_entries:
                continue

            slot_rows = {
                "bottom_ids": [[] for _ in range(len(top_entries))],
                "shoes_ids": [[] for _ in range(len(top_entries))],
                "hat_ids": [[] for _ in range(len(top_entries))],
                "underlayer_ids": [[] for _ in range(len(top_entries))],
                "overlayer_ids": [[] for _ in range(len(top_entries))],
            }

            for block in main_container.get("children", []):
                if block.get("name") not in {"Category Container", "Subcategory Container"}:
                    continue

                block_title = None
                for n in walk(block):
                    if n.get("type") == "TEXT" and n.get("name") == "Subcategory Title":
                        block_title = n.get("characters", "").strip().lower()
                        break
                if not block_title:
                    continue

                if "bottom" in block_title:
                    block_default_slot = "bottom_ids"
                elif "shoe" in block_title:
                    block_default_slot = "shoes_ids"
                elif "hat" in block_title:
                    block_default_slot = "hat_ids"
                elif "under" in block_title:
                    block_default_slot = "underlayer_ids"
                elif "over" in block_title or "jacket" in block_title or "coat" in block_title:
                    block_default_slot = "overlayer_ids"
                else:
                    continue

                container = find_child_by_name(block, "Container")
                if not container:
                    continue

                product_rows = [r for r in container.get("children", []) if r.get("name") == "Product Images"]
                for idx, row in enumerate(product_rows):
                    if idx >= len(top_entries):
                        break
                    row_ids = collect_instance_item_ids(row, component_to_item)
                    for item_id in row_ids:
                        # In mixed sections like "Under layer / Over Layer", infer the slot by item type.
                        item_type = None
                        if item_id.startswith("overlayer_"):
                            item_type = "overlayer"
                        elif item_id.startswith("hat_"):
                            item_type = "hat"
                        elif item_id.startswith("shoes_"):
                            item_type = "shoes"
                        elif item_id.startswith("bottom_"):
                            item_type = "bottom"
                        elif item_id.startswith("top_"):
                            item_type = "top"

                        if item_type == "overlayer":
                            slot = "overlayer_ids"
                        elif item_type == "top" and ("under" in block_title or "over" in block_title):
                            slot = "underlayer_ids"
                        else:
                            slot = block_default_slot

                        if item_id not in slot_rows[slot][idx]:
                            slot_rows[slot][idx].append(item_id)

            for idx, top_member_ids in enumerate(top_entries):
                if len(top_member_ids) == 1:
                    source_kind = "item"
                    source_id = top_member_ids[0]
                else:
                    source_kind = "cluster"
                    key = "|".join(sorted(top_member_ids))
                    if key not in clusters:
                        nonlocal_id = f"cluster_top_{cluster_seq:03d}"
                        clusters[key] = {
                            "cluster_id": nonlocal_id,
                            "cluster_name": f"Top cluster {cluster_seq}",
                            "type": "top",
                            "member_item_ids": sorted(top_member_ids),
                            "notes": "Auto-extracted from grouped top entries in Looks.",
                        }
                        cluster_seq += 1
                    source_id = clusters[key]["cluster_id"]

                match_base = {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "weather_bucket": weather_bucket,
                    "bottom_ids": slot_rows["bottom_ids"][idx][:4],
                    "shoes_ids": slot_rows["shoes_ids"][idx][:4],
                    "hat_ids": slot_rows["hat_ids"][idx][:4],
                    "underlayer_ids": slot_rows["underlayer_ids"][idx][:4],
                    "overlayer_ids": slot_rows["overlayer_ids"][idx][:4],
                    "priority": 1,
                }

                for occasion in occasions:
                    rec = dict(match_base)
                    rec["occasion"] = occasion
                    top_matches.append(rec)

    unique_matches = {}
    for rec in top_matches:
        key = (
            rec["source_kind"],
            rec["source_id"],
            rec["occasion"],
            rec["weather_bucket"],
        )
        unique_matches[key] = rec

    return list(clusters.values()), list(unique_matches.values())


def main():
    OUT_DIR.mkdir(exist_ok=True)

    with RAW_PATH.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    pages = {p.get("name"): p for p in doc["document"].get("children", [])}
    catalog = pages.get("Catalog")
    looks = pages.get("Looks")
    if not catalog or not looks:
        raise RuntimeError("Expected Catalog and Looks pages in Figma file.")

    component_to_item, items = extract_catalog(catalog)
    clusters, top_matches = extract_looks(looks, component_to_item)

    rules = [
        {
            "rule_id": "base_hot_warm",
            "occasion": "*",
            "weather_bucket": "hot_warm",
            "required_slots": ["top", "bottom", "shoes"],
            "forbidden_subtypes": [],
            "notes": "Hat/underlayer/overlayer optional.",
        },
        {
            "rule_id": "base_pleasant_chilly",
            "occasion": "*",
            "weather_bucket": "pleasant_chilly",
            "required_slots": ["top", "bottom", "shoes"],
            "forbidden_subtypes": [],
            "notes": "Allow optional layers based on match data.",
        },
        {
            "rule_id": "base_cold",
            "occasion": "*",
            "weather_bucket": "cold",
            "required_slots": ["top", "bottom", "shoes"],
            "forbidden_subtypes": [],
            "notes": "Prefer overlayer matches when available.",
        },
    ]

    (OUT_DIR / "items.json").write_text(json.dumps(sorted(items, key=lambda x: x["item_id"]), indent=2), encoding="utf-8")
    (OUT_DIR / "clusters.json").write_text(json.dumps(sorted(clusters, key=lambda x: x["cluster_id"]), indent=2), encoding="utf-8")
    (OUT_DIR / "top_matches.json").write_text(
        json.dumps(
            sorted(
                top_matches,
                key=lambda x: (x["weather_bucket"], x["occasion"], x["source_kind"], x["source_id"]),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "rules.json").write_text(json.dumps(rules, indent=2), encoding="utf-8")

    summary = {
        "items": len(items),
        "clusters": len(clusters),
        "top_matches": len(top_matches),
    }
    (OUT_DIR / "extract_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
