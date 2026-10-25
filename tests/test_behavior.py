"""Consumer-visible timer, hook and HTTP security boundaries."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipclock.model import Companion
from pipclock.server import create_server


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pip = Companion(clock=lambda: self.now)

    def test_message_expiry_restores_current_event_not_previous_one(self):
        self.pip.message("Build complete", 5)
        self.now += 2
        self.pip.event("thinking", 20)
        self.now += 3
        state = self.pip.snapshot()
        self.assertIsNone(state["message"])
        self.assertEqual(state["state"], "thinking")
        self.assertEqual(state["elapsed"], 3)

    def test_repeated_thinking_extends_watchdog_without_restarting_animation(self):
        self.pip.event("thinking", 10)
        self.now += 9
        self.pip.event("thinking", 10)
        self.now += 2
        self.assertEqual(self.pip.snapshot()["elapsed"], 11)
        self.assertEqual(self.pip.snapshot()["state"], "thinking")
        self.now += 8
        self.assertEqual(self.pip.snapshot()["state"], "idle")

    def test_retriggering_scared_replays_the_run_instead_of_resuming_offscreen(self):
        self.pip.event("scared", 8)
        self.now += 3
        self.pip.event("scared", 8)
        self.assertEqual(self.pip.snapshot()["elapsed"], 0)
        self.now += 7
        self.assertEqual(self.pip.snapshot()["state"], "scared")
        self.now += 1
        self.assertEqual(self.pip.snapshot()["state"], "idle")

    def test_latest_note_replaces_old_note_and_has_independent_deadline(self):
        self.pip.message("Old note", 100)
        self.now += 1
        self.pip.message("New note", 2)
        self.pip.event("dance", 1)
        self.now += 1
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["message"], "New note")
        self.now += 1
        self.assertIsNone(self.pip.snapshot()["message"])

    def test_stop_celebrates_then_returns_to_idle(self):
        self.pip.claude({"hook_event_name": "UserPromptSubmit", "prompt": "private"})
        self.now += 5
        self.pip.claude({"hook_event_name": "Stop"})
        self.assertEqual(self.pip.snapshot()["state"], "bounce")
        self.now += 8
        self.assertEqual(self.pip.snapshot()["state"], "idle")
        self.assertNotIn("prompt", self.pip.snapshot())

    def test_invalid_messages_do_not_replace_live_note(self):
        self.pip.message("Keep me", 10)
        for text, duration in [("", 1), (" " * 280, 1), ("x" * 281, 1), ("tab\t", 1), ("x", True), ("x", 0), ("x", float("nan")), ("x", float("inf")), ("x", 3601), ("x", 10**500)]:
            with self.subTest(text=text[:8], duration=duration):
                with self.assertRaises(ValueError):
                    self.pip.message(text, duration)
        self.assertEqual(self.pip.snapshot()["message"], "Keep me")


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pip = Companion()
        cls.server = create_server("127.0.0.1", 0, cls.pip, token="test-secret")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, payload=None, authorized=True, content_type="application/json"):
        headers = {"Content-Type": content_type}
        if authorized:
            headers["Authorization"] = "Bearer test-secret"
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(self.base + path, data=body, headers=headers)
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_unauthorized_requests_cannot_mutate_or_read_state(self):
        self.pip.event("idle")
        status, _ = self.request("/api/event", {"event": "dance"}, authorized=False)
        self.assertEqual(status, 401)
        status, _ = self.request("/api/state", authorized=False)
        self.assertEqual(status, 401)
        self.assertEqual(self.pip.snapshot()["state"], "idle")

    def test_hook_response_cannot_block_or_inject_context_into_claude(self):
        status, body = self.request("/hooks/claude", {"hook_event_name": "PermissionRequest", "tool_input": {"command": "private"}})
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(self.pip.snapshot()["state"], "waiting")
        self.assertNotIn("tool_input", self.pip.snapshot())

    def test_browser_form_and_invalid_values_cannot_mutate_state(self):
        self.pip.event("idle")
        cases = [({"event": "dance"}, "text/plain", 415), ({"event": []}, "application/json", 400), ({"event": "bored"}, "application/json", 400), ({"event": "dance", "duration": -1}, "application/json", 400), (["dance"], "application/json", 400), ({"event": "dance", "padding": "x" * 16384}, "application/json", 413)]
        for payload, content_type, expected in cases:
            with self.subTest(expected=expected, payload_type=type(payload).__name__):
                status, _ = self.request("/api/event", payload, content_type=content_type)
                self.assertEqual(status, expected)
                self.assertEqual(self.pip.snapshot()["state"], "idle")


if __name__ == "__main__":
    unittest.main()
