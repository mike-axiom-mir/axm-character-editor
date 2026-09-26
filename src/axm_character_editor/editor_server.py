"""Loopback-only character builder for the browser editor; Python standard library only."""
from __future__ import annotations

import io
import json
import secrets
import threading
import zipfile
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from .blueprint import BlueprintError, validate_blueprint
from .human_asset import build_glb, build_package

MAX_BODY = 64 * 1024


@lru_cache(maxsize=4)
def compile_preview(canonical: str) -> tuple[bytes, dict]:
    return build_glb(json.loads(canonical))


def package_bytes(blueprint: dict) -> bytes:
    with TemporaryDirectory(prefix="axm-character-") as tmp:
        target = Path(tmp) / "character"
        build_package(blueprint, target)
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(target).as_posix())
        return result.getvalue()


def editor_html() -> str:
    # The generated HTML is also included in wheels, so serve works outside a checkout.
    path = Path(__file__).parent / "data" / "editor" / "character-editor.html"
    if not path.is_file():
        raise FileNotFoundError("Build the editor first: python tools/build_editor.py")
    return path.read_text(encoding="utf-8")


def create_server(port: int = 8765) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(32)
    work = threading.Lock()
    source = editor_html()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status: int, body: bytes, content_type: str, **headers):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for key, value in headers.items():
                self.send_header(key.replace("_", "-"), str(value))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def error(self, status: int, message: str):
            self.reply(status, json.dumps({"error": message}).encode(), "application/json")

        def local_request(self) -> bool:
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts:
                self.error(403, "Use the local editor address printed in your terminal.")
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in hosts}:
                self.error(403, "Cross-origin builder requests are not accepted.")
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            if self.path != "/":
                self.error(404, "Not found")
                return
            config = json.dumps({"token": token})
            body = source.replace("const SERVER=null;", "const SERVER=" + config + ";")
            self.reply(200, body.encode(), "text/html; charset=utf-8")

        def do_POST(self):
            if not self.local_request():
                return
            if self.path not in ("/api/preview", "/api/package"):
                self.error(404, "Not found")
                return
            if not secrets.compare_digest(self.headers.get("X-AXM-Token", ""), token):
                self.error(403, "Reopen the editor from the local server.")
                return
            if self.headers.get_content_type() != "application/json":
                self.error(415, "Send a JSON character blueprint.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= MAX_BODY:
                self.error(413, "Blueprint must be between 1 and 65536 bytes.")
                return
            self.connection.settimeout(10)
            try:
                blueprint = validate_blueprint(json.loads(self.rfile.read(length)))
            except (BlueprintError, ValueError, UnicodeError, TimeoutError) as exc:
                self.error(400, str(exc))
                return
            if not work.acquire(blocking=False):
                self.error(503, "The builder is busy. Try again in a moment.")
                return
            try:
                if self.path == "/api/preview":
                    body, receipt = compile_preview(json.dumps(blueprint, sort_keys=True, allow_nan=False))
                    self.reply(200, body, "model/gltf-binary", X_AXM_Vertices=receipt["vertices"],
                               X_AXM_Triangles=receipt["triangles"], X_AXM_SHA256=receipt["sha256"])
                else:
                    self.reply(200, package_bytes(blueprint), "application/zip",
                               Content_Disposition='attachment; filename="character-package.zip"')
            except Exception:
                self.error(500, "The character build failed. Your blueprint has been kept; see the local builder.")
                import traceback
                traceback.print_exc()
            finally:
                work.release()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve(port: int = 8765) -> None:
    with create_server(port) as server:
        print(f"AXM Character Editor: http://127.0.0.1:{server.server_port}/", flush=True)
        print("Local builder connected. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
