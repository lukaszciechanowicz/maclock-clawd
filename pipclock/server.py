"""Small local API and optional desktop-only frame mirror."""

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit

MAX_BODY = 16 * 1024


class Frames:
    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = None

    def put(self, jpeg):
        with self._lock:
            self._jpeg = jpeg

    def get(self):
        with self._lock:
            return self._jpeg


def create_server(host, port, companion, frames=None, token=None):
    preview = Path(__file__).with_name("preview.html").read_bytes() if frames else None

    class Handler(BaseHTTPRequestHandler):
        server_version = "PipClock/0.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            # Hook payloads, tokens and custom messages never enter access logs.
            pass

        def reply(self, status, body=b"", content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def json_reply(self, status, value):
            self.reply(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def authorized(self):
            supplied = self.headers.get("Authorization", "").encode("utf-8")
            if token and not hmac.compare_digest(supplied, ("Bearer " + token).encode("utf-8")):
                self.json_reply(401, {"error": "a valid bearer token is required"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/health":
                self.json_reply(200, {"status": "ok", "preview": frames is not None})
            elif path == "/api/state":
                if self.authorized():
                    self.json_reply(200, companion.snapshot())
            elif path == "/" and preview:
                self.reply(200, preview, "text/html; charset=utf-8")
            elif path == "/frame.jpg" and frames:
                jpeg = frames.get()
                if jpeg:
                    self.reply(200, jpeg, "image/jpeg")
                else:
                    self.json_reply(503, {"error": "first frame is not ready"})
            else:
                self.json_reply(404, {"error": "not found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in ("/api/event", "/api/message", "/hooks/claude"):
                self.json_reply(404, {"error": "not found"})
                return
            if not self.authorized():
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self.json_reply(415, {"error": "Content-Type must be application/json"})
                return
            if self.headers.get("Transfer-Encoding"):
                self.json_reply(400, {"error": "chunked requests are not supported"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= MAX_BODY:
                self.json_reply(413, {"error": "body must contain 1 to 16384 bytes"})
                return
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("incomplete request body")
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError("body must be a JSON object")
                if path == "/api/event":
                    companion.event(payload.get("event"), payload.get("duration"))
                elif path == "/api/message":
                    companion.message(payload.get("text"), payload.get("duration"))
                else:
                    companion.claude(payload)
            except (ValueError, UnicodeError, RecursionError) as error:
                self.json_reply(400, {"error": str(error)})
                return
            except TimeoutError:
                self.json_reply(408, {"error": "request body timed out"})
                return
            if path == "/hooks/claude":
                self.reply(204)
            else:
                self.json_reply(200, companion.snapshot())

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
