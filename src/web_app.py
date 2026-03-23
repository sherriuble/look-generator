import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from wardrobe_engine import VALID_OCCASIONS, VALID_WEATHERS, WardrobeEngine


ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
ENGINE = WardrobeEngine(ROOT)


class WardrobeHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404, "Not Found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(WEB_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        if path == "/styles.css":
            self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if path.startswith("/assets/"):
            # Serve generated images
            asset_path = ROOT / path.lstrip("/")
            ext = asset_path.suffix.lower()
            ctype = "image/png" if ext == ".png" else "application/octet-stream"
            self._send_file(asset_path, ctype)
            return
        if path == "/api/meta":
            self._send_json(
                {
                    "weathers": sorted(VALID_WEATHERS),
                    "occasions": sorted(VALID_OCCASIONS),
                }
            )
            return
        if path == "/api/generate":
            qs = parse_qs(parsed.query)
            weather = (qs.get("weather") or [None])[0]
            occasion = (qs.get("occasion") or [None])[0]
            layer_mode = (qs.get("layer_mode") or ["auto"])[0]
            seed_raw = (qs.get("seed") or [None])[0]
            seed = int(seed_raw) if seed_raw and seed_raw.isdigit() else None
            if not weather or not occasion:
                self._send_json({"error": "Missing weather or occasion query params."}, status=400)
                return
            try:
                result = ENGINE.generate(weather=weather, occasion=occasion, seed=seed, layer_mode=layer_mode)
                self._send_json(result)
            except ValueError as e:
                self._send_json({"error": str(e)}, status=400)
            return

        self.send_error(404, "Not Found")


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    server = HTTPServer((host, port), WardrobeHandler)
    print(f"Wardrobe generator running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
