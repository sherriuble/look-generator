#!/usr/bin/env python3
"""
Fetch a Figma node JSON via REST API (for design handoff / CSS alignment).

Usage:
  export FIGMA_TOKEN=figd_...
  python3 scripts/figma_fetch_node.py

Optional env:
  FIGMA_FILE_KEY   default: fjctaZ8WnOnMwH9JcMEjyc (Anya's Wardrobe)
  FIGMA_NODE_ID    default: 242:2729 (from URL node-id=242-2729)

Token: use FIGMA_TOKEN, or FIGMA_API_KEY (same as many MCP configs).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

FILE_KEY = os.environ.get("FIGMA_FILE_KEY", "fjctaZ8WnOnMwH9JcMEjyc")
# URL uses 242-2729; API expects 242:2729
RAW_NODE = os.environ.get("FIGMA_NODE_ID", "242:2729")


def main():
    token = os.environ.get("FIGMA_TOKEN") or os.environ.get("FIGMA_API_KEY")
    if not token:
        print(
            "Missing FIGMA_TOKEN or FIGMA_API_KEY.\n"
            "  export FIGMA_TOKEN=your_personal_access_token\n"
            "  # or: export FIGMA_API_KEY=...\n"
            "Then re-run this script.\n"
            "(MCP in Cursor does not pass the key to this sandbox — run once in your own terminal.)",
            file=sys.stderr,
        )
        sys.exit(1)

    q = urllib.parse.urlencode({"ids": RAW_NODE})
    url = f"https://api.figma.com/v1/files/{FILE_KEY}/nodes?{q}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"HTTP {e.code}: {body[:800]}", file=sys.stderr)
        sys.exit(1)

    out = os.environ.get("FIGMA_NODE_JSON", "figma_node_dump.json")
    path = os.path.join(os.path.dirname(__file__), out)
    path = os.path.normpath(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {path}")
    nodes = data.get("nodes", {})
    if RAW_NODE in nodes:
        doc = nodes[RAW_NODE].get("document", {})
        print("Node name:", doc.get("name", "?"))
        print("Type:", doc.get("type", "?"))


if __name__ == "__main__":
    main()
