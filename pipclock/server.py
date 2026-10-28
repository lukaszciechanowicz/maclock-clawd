"""Small local API and optional desktop-only frame mirror."""

import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import parse_qsl, urlsplit

from .model import DEFAULT_TEXT_SIZE

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

        def same_origin_reaction(self):
            sites = self.headers.get_all("Sec-Fetch-Site", [])
            if any(site.strip().lower() == "cross-site"
                   for value in sites for site in value.split(",")):
                return False
            origins = self.headers.get_all("Origin", [])
            if not origins:
                return True
            hosts = self.headers.get_all("Host", [])
            if len(origins) != 1 or len(hosts) != 1:
                return False
            try:
                origin = urlsplit(origins[0])
                target = urlsplit("http://" + hosts[0])
                for value in (origin, target):
                    if (value.scheme != "http" or not value.hostname
                            or value.username is not None or value.password is not None
                            or value.path or value.query or value.fragment):
                        return False
                origin_port = 80 if origin.port is None else origin.port
                target_port = 80 if target.port is None else target.port
                return (origin.hostname, origin_port) == (target.hostname, target_port)
            except ValueError:
                return False

        def react(self, query):
            if not self.authorized():
                return
            if not self.same_origin_reaction():
                self.json_reply(403, {"error": "cross-origin reactions are not allowed"})
                return
            try:
                if re.search(r"%(?![0-9a-fA-F]{2})", query):
                    raise ValueError("invalid percent escape in query")
                pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True,
                                  errors="strict", max_num_fields=4)
                parameters = {}
                for name, value in pairs:
                    if name not in ("mood", "text", "duration", "text_size") or name in parameters:
                        raise ValueError("query parameters must be unique mood, text, optional duration and text_size")
                    parameters[name] = value
                if "mood" not in parameters or "text" not in parameters:
                    raise ValueError("mood and text query parameters are required")
                duration = float(parameters["duration"]) if "duration" in parameters else 8
                text_size = DEFAULT_TEXT_SIZE
                if "text_size" in parameters:
                    if not re.fullmatch(r"[+-]?[0-9]+", parameters["text_size"]):
                        raise ValueError("text_size must be an integer")
                    text_size = int(parameters["text_size"])
                companion.react(parameters["mood"], parameters["text"], duration, text_size)
            except (ValueError, UnicodeError) as error:
                self.json_reply(400, {"error": str(error)})
                return
            self.json_reply(200, companion.snapshot())

        def do_GET(self):
            request = urlsplit(self.path)
            path = request.path
            if path == "/health":
                self.json_reply(200, {"status": "ok", "preview": frames is not None})
            elif path == "/api/state":
                if self.authorized():
                    self.json_reply(200, companion.snapshot())
            elif path == "/api/react":
                self.react(request.query)
            elif path == "/api/idle":
                if self.authorized():
                    self.json_reply(200, companion.idle_config())
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
            if path not in ("/api/event", "/api/message", "/api/idle", "/hooks/claude"):
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
                    companion.message(payload.get("text"), payload.get("duration"),
                                      payload.get("text_size", DEFAULT_TEXT_SIZE))
                elif path == "/api/idle":
                    try:
                        config = companion.configure_idle(payload.get("actions"), payload.get("interval"))
                    except OSError:
                        self.json_reply(500, {"error": "could not persist idle configuration"})
                        return
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
            elif path == "/api/idle":
                self.json_reply(200, config)
            else:
                self.json_reply(200, companion.snapshot())

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
