import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "figma_raw.json"
ITEMS_PATH = ROOT / "data" / "items.json"
ASSETS_DIR = ROOT / "assets"
THUMBS_DIR = ASSETS_DIR / "thumbs"
FULL_DIR = ASSETS_DIR / "full"
MAP_PATH = ROOT / "data" / "image_map.json"

FILE_KEY = "fjctaZ8WnOnMwH9JcMEjyc"
FIGMA_TOKEN = None


def parse_mode_and_item(component_name: str):
    mode = None
    item = None
    for part in component_name.split(","):
        part = part.strip()
        if part.startswith("Mode="):
            mode = part.split("=", 1)[1].strip().lower()
        elif part.startswith("Item="):
            item = part.split("=", 1)[1].strip()
    return mode, item


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"X-Figma-Token": FIGMA_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Figma API error {e.code}: {body[:500]}")


def download_file(url: str, out_path: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "wardrobe-exporter/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    out_path.write_bytes(data)


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def main():
    figma_token = os.environ.get("FIGMA_TOKEN")
    if not figma_token:
        raise SystemExit("Missing FIGMA_TOKEN env var. Run: FIGMA_TOKEN=... python3 scripts/export_figma_images.py")

    global FIGMA_TOKEN
    FIGMA_TOKEN = figma_token

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    components = raw.get("components", {})

    # Build best component ids for each item (prefer image-only for thumbs, info/full for full).
    id_to_component = {}
    for cid, cmeta in components.items():
        id_to_component[cid] = cmeta.get("name", "")

    image_plan = []
    for item in items:
        cids = item.get("figma_component_ids", [])
        thumb_cid = None
        full_cid = None
        fallback_cid = cids[0] if cids else None
        for cid in cids:
            cname = id_to_component.get(cid, "")
            mode, _ = parse_mode_and_item(cname)
            if mode == "image only":
                thumb_cid = thumb_cid or cid
            if mode in {"info", "full"}:
                full_cid = full_cid or cid
        thumb_cid = thumb_cid or fallback_cid
        full_cid = full_cid or fallback_cid
        if thumb_cid or full_cid:
            image_plan.append(
                {
                    "item_id": item["item_id"],
                    "thumb_cid": thumb_cid,
                    "full_cid": full_cid,
                }
            )

    thumb_ids = sorted({p["thumb_cid"] for p in image_plan if p["thumb_cid"]})
    full_ids = sorted({p["full_cid"] for p in image_plan if p["full_cid"]})

    def get_image_urls(component_ids, scale):
        urls = {}
        for batch in chunked(component_ids, 25):
            ids_str = ",".join(batch)
            q = urllib.parse.urlencode({"ids": ids_str, "format": "png", "scale": str(scale)})
            endpoint = f"https://api.figma.com/v1/images/{FILE_KEY}?{q}"
            payload = fetch_json(endpoint)
            urls.update(payload.get("images", {}))
        return urls

    thumb_urls = get_image_urls(thumb_ids, scale=1)
    full_urls = get_image_urls(full_ids, scale=2)

    image_map = {}
    downloaded = {"thumbs": 0, "full": 0}
    errors = []

    for plan in image_plan:
        item_id = plan["item_id"]
        rec = {"item_id": item_id}

        thumb_url = thumb_urls.get(plan["thumb_cid"]) if plan["thumb_cid"] else None
        if thumb_url:
            thumb_path = THUMBS_DIR / f"{item_id}.png"
            try:
                download_file(thumb_url, thumb_path)
                rec["thumb"] = str(thumb_path.relative_to(ROOT))
                downloaded["thumbs"] += 1
            except (urllib.error.URLError, TimeoutError) as e:
                errors.append(f"thumb:{item_id}:{e}")

        full_url = full_urls.get(plan["full_cid"]) if plan["full_cid"] else None
        if full_url:
            full_path = FULL_DIR / f"{item_id}.png"
            try:
                download_file(full_url, full_path)
                rec["full"] = str(full_path.relative_to(ROOT))
                downloaded["full"] += 1
            except (urllib.error.URLError, TimeoutError) as e:
                errors.append(f"full:{item_id}:{e}")

        image_map[item_id] = rec

    MAP_PATH.write_text(json.dumps(image_map, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "planned_items": len(image_plan),
                "thumb_candidates": len(thumb_ids),
                "full_candidates": len(full_ids),
                "downloaded": downloaded,
                "errors": len(errors),
            },
            indent=2,
        )
    )
    if errors:
        print("Sample errors:")
        for e in errors[:10]:
            print("-", e)


if __name__ == "__main__":
    main()
