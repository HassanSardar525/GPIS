"""Dependency-free HTTP server for the first GPIS vertical slice."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from app.retrieval import EvidenceRetriever, generate_grounded_answer
from app.scoring import rankings, score_districts


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
DATA = json.loads((ROOT / "data" / "curated" / "districts.json").read_text(encoding="utf-8"))
DISTRICTS = score_districts(DATA["districts"])
BY_SLUG = {district["slug"]: district for district in DISTRICTS}
RETRIEVER = EvidenceRetriever(DISTRICTS, DATA["sources"])


def payload_for(district: dict) -> dict:
    return {
        **district,
        "rankings": {
            category: next(item for item in rankings(DISTRICTS, category) if item["slug"] == district["slug"])
            for category in ("overall", "education", "health", "accountability")
        },
        "sources": DATA["sources"],
        "metadata": DATA["metadata"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GPISPrototype/0.1"

    def _json(self, body: object, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _static(self, relative_path: str) -> None:
        requested = (STATIC / relative_path).resolve()
        if STATIC.resolve() not in requested.parents and requested != STATIC.resolve():
            self._json({"error": "Not found"}, 404)
            return
        if not requested.is_file():
            self._json({"error": "Not found"}, 404)
            return
        content = requested.read_bytes()
        content_type, _ = mimetypes.guess_type(requested.name)
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._static("index.html")
        elif parsed.path.startswith("/static/"):
            self._static(parsed.path.removeprefix("/static/"))
        elif parsed.path == "/api/health":
            self._json({"status": "ok", "districts": len(DISTRICTS)})
        elif parsed.path == "/api/districts":
            self._json(
                {
                    "districts": [
                        {"slug": district["slug"], "name": district["name"], "scores": district["derived"]["scores"]}
                        for district in DISTRICTS
                    ],
                    "metadata": DATA["metadata"],
                }
            )
        elif parsed.path.startswith("/api/districts/"):
            slug = unquote(parsed.path.removeprefix("/api/districts/")).strip("/")
            district = BY_SLUG.get(slug)
            self._json(payload_for(district), 200) if district else self._json({"error": "District not found"}, 404)
        elif parsed.path == "/api/rankings":
            category = parse_qs(parsed.query).get("category", ["overall"])[0]
            try:
                self._json({"category": category, "rankings": rankings(DISTRICTS, category)})
            except ValueError as error:
                self._json({"error": str(error)}, 400)
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/chat":
            self._json({"error": "Not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            question = str(request.get("question", "")).strip()
            district = request.get("district")
            if not question:
                self._json({"error": "question is required"}, 400)
                return
            results = RETRIEVER.search(question, district_slug=district)
            self._json(generate_grounded_answer(question, results))
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": f"Invalid request: {error}"}, 400)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[GPIS] {self.address_string()} - {format % args}")


def main() -> None:
    address = ("127.0.0.1", 8000)
    print(f"GPIS prototype running at http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, Handler).serve_forever()


if __name__ == "__main__":
    main()
