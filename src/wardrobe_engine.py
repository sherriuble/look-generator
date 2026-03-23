import json
import random
from pathlib import Path


VALID_WEATHERS = {"hot_warm", "pleasant_chilly", "cold"}
VALID_OCCASIONS = {"sport", "casual", "work", "nice"}


class WardrobeEngine:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.items = self._load_json(self.data_dir / "items.json")
        self.clusters = self._load_json(self.data_dir / "clusters.json")
        self.matches = self._load_json(self.data_dir / "top_matches.json")
        self.image_map = self._load_json(self.data_dir / "image_map.json")
        self.history_path = self.data_dir / "outfit_history.json"
        self.item_index = {i["item_id"]: i for i in self.items}
        self.cluster_index = {c["cluster_id"]: c for c in self.clusters}

    def _load_json(self, path: Path):
        if not path.exists():
            return [] if path.name.endswith(".json") and path.name != "image_map.json" else {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_history(self, history):
        self.history_path.write_text(json.dumps(history[-500:], indent=2), encoding="utf-8")

    def _format_item(self, item_id):
        item = self.item_index.get(item_id)
        image = self.image_map.get(item_id, {})
        if not item:
            return {"item_id": item_id, "name": item_id, "type": "unknown"}
        return {
            "item_id": item["item_id"],
            "name": item["name"],
            "type": item["type"],
            "subtype": item.get("subtype"),
            "image_thumb": image.get("thumb"),
            "image_full": image.get("full"),
        }

    def _source_top_ids(self, match):
        if match["source_kind"] == "item":
            return [match["source_id"]]
        cluster = self.cluster_index.get(match["source_id"])
        return cluster["member_item_ids"] if cluster else []

    def _is_dress_match(self, match, top_ids):
        # Treat a match as dress-based when any source top is a dress subtype.
        for top_id in top_ids:
            item = self.item_index.get(top_id)
            if item and item.get("subtype") == "dress":
                return True
        if match.get("source_kind") == "item":
            item = self.item_index.get(match.get("source_id"))
            return bool(item and item.get("subtype") == "dress")
        return False

    def _load_history(self):
        if not self.history_path.exists():
            return []
        return json.loads(self.history_path.read_text(encoding="utf-8"))

    def _pick_candidate(self, weather, occasion, history, layer_mode="auto"):
        candidates = []
        for m in self.matches:
            if m.get("weather_bucket") != weather or m.get("occasion") != occasion:
                continue
            top_ids = self._source_top_ids(m)
            if not top_ids:
                continue
            is_dress = self._is_dress_match(m, top_ids)
            has_bottom = bool(m.get("bottom_ids"))
            has_shoes = bool(m.get("shoes_ids"))
            # Dresses can be valid without bottoms; non-dress looks require bottoms.
            if not has_shoes or (not is_dress and not has_bottom):
                continue
            key = f"{weather}|{occasion}|{m['source_kind']}|{m['source_id']}"
            item = dict(m)
            item["match_key"] = key
            candidates.append(item)

        if not candidates:
            raise ValueError(f"No matching look candidates for {weather} + {occasion}.")

        recent_keys = {
            h["match_key"]
            for h in history
            if h.get("weather") == weather and h.get("occasion") == occasion and h.get("match_key")
        }
        base_pool = [c for c in candidates if c["match_key"] not in recent_keys] or candidates

        def has_layers(rec):
            return bool(rec.get("underlayer_ids") or rec.get("overlayer_ids"))

        if layer_mode == "required":
            layered = [c for c in base_pool if has_layers(c)]
            if layered:
                return random.choice(layered)
            raise ValueError(f"No layered look candidates for {weather} + {occasion}.")

        if layer_mode == "prefer":
            layered = [c for c in base_pool if has_layers(c)]
            if layered:
                return random.choice(layered)
            return random.choice(base_pool)

        if layer_mode == "auto":
            # In colder weather, bias toward looks that include a layer when available.
            if weather in {"pleasant_chilly", "cold"}:
                layered = [c for c in base_pool if has_layers(c)]
                if layered:
                    return random.choice(layered)
            return random.choice(base_pool)

        return random.choice(base_pool)

    def generate(self, weather, occasion, seed=None, layer_mode="auto"):
        if weather not in VALID_WEATHERS:
            raise ValueError(f"Invalid weather: {weather}")
        if occasion not in VALID_OCCASIONS:
            raise ValueError(f"Invalid occasion: {occasion}")
        if seed is not None:
            random.seed(seed)

        history = self._load_history()
        selected = self._pick_candidate(weather, occasion, history, layer_mode=layer_mode)
        top_ids = self._source_top_ids(selected)
        if not top_ids:
            raise ValueError("Selected candidate has no resolvable top source.")

        result = {
            "weather": weather,
            "occasion": occasion,
            "top": self._format_item(random.choice(top_ids)),
            "bottom": self._format_item(random.choice(selected["bottom_ids"])) if selected.get("bottom_ids") else None,
            "shoes": self._format_item(random.choice(selected["shoes_ids"])),
            "hat": self._format_item(random.choice(selected["hat_ids"])) if selected.get("hat_ids") else None,
            "underlayer": self._format_item(random.choice(selected["underlayer_ids"]))
            if selected.get("underlayer_ids")
            else None,
            "overlayer": self._format_item(random.choice(selected["overlayer_ids"]))
            if selected.get("overlayer_ids")
            else None,
            "match_key": selected["match_key"],
        }

        history.append(
            {
                "weather": weather,
                "occasion": occasion,
                "match_key": selected["match_key"],
            }
        )
        self._save_history(history)
        return result
