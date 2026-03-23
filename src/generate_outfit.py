import argparse
import json
from pathlib import Path

from wardrobe_engine import WardrobeEngine


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Generate an outfit from extracted wardrobe data.")
    parser.add_argument("--weather", required=True, choices=["hot_warm", "pleasant_chilly", "cold"])
    parser.add_argument("--occasion", required=True, choices=["sport", "casual", "work", "nice"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--layer-mode", choices=["auto", "prefer", "required"], default="auto")
    args = parser.parse_args()

    engine = WardrobeEngine(ROOT)
    print(json.dumps(engine.generate(args.weather, args.occasion, seed=args.seed, layer_mode=args.layer_mode), indent=2))


if __name__ == "__main__":
    main()
