"""Strata web server: REST API plus the static dashboard."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from strata import storage, treemap
from strata.engine import StrataEngine
from strata.format import human_size
from strata.recommender import total_reclaimable
from strata.scanner import find_node

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class _State:
    def __init__(self, root: str):
        self.root = root
        self.eng = StrataEngine(root)
        self.lock = threading.Lock()

    def ensure(self, rebuild=False, hash_files=True):
        with self.lock:
            if rebuild or not storage.report_exists(self.root):
                self.eng.scan(hash_files=hash_files)
            else:
                self.eng.load()
        return self

    def refresh(self):
        with self.lock:
            self.eng.scan()
        return self.eng.report


def _make_handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Strata/0.1"

        def log_message(self, fmt, *args):
            return

        def _send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, rel_path: str):
            safe = os.path.normpath(rel_path).lstrip(os.sep)
            full = os.path.join(WEB_DIR, safe)
            if not os.path.abspath(full).startswith(os.path.abspath(WEB_DIR)):
                self.send_error(403)
                return
            if os.path.isdir(full) or safe == "":
                full = os.path.join(WEB_DIR, "index.html")
            if not os.path.exists(full):
                self.send_error(404)
                return
            ext = os.path.splitext(full)[1].lower()
            with open(full, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                _CONTENT_TYPES.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            try:
                if path == "/api/report":
                    self._send_json(state.eng.report.to_dict())
                    return

                if path == "/api/duplicates":
                    self._send_json({"groups": state.eng.report.duplicates})
                    return

                if path == "/api/recommendations":
                    threshold = int(params.get("threshold_mb", ["50"])[0])
                    recs = state.eng.recommendations(
                        large_threshold=threshold * 1024 * 1024)
                    self._send_json({
                        "recommendations": [r.to_dict() for r in recs],
                        "estimated_reclaimable": total_reclaimable(recs),
                    })
                    return

                if path == "/api/treemap":
                    depth = int(params.get("depth", ["2"])[0])
                    node_path = params.get("path", [""])[0]
                    root = state.eng.tree
                    node = find_node(root, node_path) if node_path else root
                    if node is None:
                        self._send_json({"error": "not found"}, 404)
                        return
                    rects = treemap.treemap_nodes(
                        node, (0, 0, 1000, 1000),
                        max_depth=max(1, depth))
                    self._send_json({
                        "path": "" if node is root else node.path,
                        "name": node.name,
                        "size": node.size, "is_dir": node.is_dir,
                        "rects": rects,
                    })
                    return

                if path == "/api/sunburst":
                    depth = int(params.get("depth", ["3"])[0])
                    sectors = treemap.sunburst(
                        state.eng.tree, 0.28, 0.55,
                        max_depth=max(1, depth))
                    self._send_json({
                        "name": state.eng.tree.name,
                        "size": state.eng.tree.size,
                        "sectors": sectors,
                    })
                    return

                if path == "/api/node":
                    node_path = params.get("path", [""])[0]
                    node = find_node(state.eng.tree, node_path)
                    if node is None:
                        self._send_json({"error": "not found"}, 404)
                        return
                    self._send_json(node.to_dict())
                    return

                if path == "/api/refresh":
                    report = state.refresh()
                    self._send_json(report.to_dict())
                    return

                if path == "/api/health":
                    self._send_json({"status": "ok"})
                    return

                if path.startswith("/api/"):
                    self.send_error(404)
                    return

                self._send_static(path.lstrip("/"))
            except BrokenPipeError:
                pass
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

    return Handler


def serve(root: str, host: str = "127.0.0.1", port: int = 8850,
          hash_files: bool = True, rebuild: bool = False) -> int:
    if not os.path.exists(root):
        print(f"error: path not found: {root}")
        return 1
    state = _State(root)
    print(f"Scanning {os.path.abspath(root)} ...")
    state.ensure(rebuild=rebuild, hash_files=hash_files)
    r = state.eng.report
    print(f"Mapped {r.file_count} files, {human_size(r.total_size)} "
          f"in {r.scan_time:.2f}s.")

    httpd = ThreadingHTTPServer((host, port), _make_handler(state))
    url = f"http://{host}:{port}"
    print(f"Strata dashboard running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0
