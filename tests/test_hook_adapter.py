"""Exercise the opt-in command adapter against a real local HTTP listener."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import unittest


ADAPTER = Path(__file__).resolve().parents[1] / "examples" / "pipclock_hook.py"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.requests.put((self.path, dict(self.headers), body))
        if self.server.delay:
            time.sleep(self.server.delay)
        self.send_response(self.server.response_code)
        if self.server.response_code == 302:
            self.send_header("Location", "/redirect-target")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.server.requests.put((self.path, dict(self.headers), b""))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


@unittest.skipUnless(hasattr(signal, "ITIMER_REAL"), "POSIX adapter deadline")
class HookAdapterTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = queue.Queue()
        self.server.delay = 0
        self.server.response_code = 200
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.environment = {
            **os.environ,
            "PIPCLOCK_URL": "http://127.0.0.1:" + str(self.server.server_port),
            "PIPCLOCK_TOKEN": "test-display-token",
            "PIPCLOCK_FINISHED": "dance",
            "PIPCLOCK_HOOKS_DISABLED": "0",
        }

    def run_adapter(self, *args, payload="", **environment):
        result = subprocess.run(
            [sys.executable, str(ADAPTER), *args], input=payload,
            text=True, capture_output=True, timeout=4,
            env={**self.environment, **environment},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        if args[0] == "codex":
            self.assertEqual(json.loads(result.stdout), {})
        else:
            self.assertEqual(result.stdout, "")
        return result

    def expect_event(self, event):
        path, headers, body = self.server.requests.get_nowait()
        self.assertEqual(path, "/api/event")
        self.assertEqual(headers["Authorization"], "Bearer test-display-token")
        self.assertEqual(json.loads(body), {"event": event})
        self.assertTrue(self.server.requests.empty())

    def test_completion_sends_no_private_payload_or_hook_decision(self):
        for platform in ("claude", "codex"):
            with self.subTest(platform=platform):
                self.run_adapter(platform, payload=json.dumps({
                    "hook_event_name": "Stop", "prompt": "private prompt",
                    "tool_input": {"command": "private arguments"},
                    "cwd": "/private/path", "transcript_path": "/private/transcript",
                    "last_assistant_message": "private response",
                }))
                self.expect_event("dance")

    def test_finished_selection_excludes_easter_eggs(self):
        self.run_adapter("action", "finish", PIPCLOCK_FINISHED="pool")
        self.expect_event("pool")
        self.run_adapter("action", "finish", PIPCLOCK_FINISHED="windows_bsod")
        self.assertTrue(self.server.requests.empty())

    def test_opt_out_invalid_input_and_missing_token_do_not_post(self):
        self.run_adapter("action", "finish", PIPCLOCK_HOOKS_DISABLED="1")
        self.run_adapter("action", "finish", PIPCLOCK_TOKEN="")
        self.run_adapter("claude", payload="not JSON")
        self.run_adapter("codex", payload='{"hook_event_name":"Unknown"}')
        self.assertTrue(self.server.requests.empty())

    def test_auth_failure_is_observational_and_redirect_is_not_followed(self):
        for status in (401, 302):
            with self.subTest(status=status):
                self.server.response_code = status
                self.run_adapter("codex", payload='{"hook_event_name":"Stop"}')
                self.expect_event("dance")

    def test_slow_http_is_bounded_and_fail_open(self):
        self.server.delay = 3
        started = time.monotonic()
        self.run_adapter("action", "finish")
        self.assertLess(time.monotonic() - started, 3.5)
        self.expect_event("dance")


if __name__ == "__main__":
    unittest.main()
