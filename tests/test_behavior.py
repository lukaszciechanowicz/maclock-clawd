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


    def test_reaction_caption_and_animation_expire_together_without_changing_note(self):
        self.pip.message("Bottom note", 30)
        self.pip.react("flag_pl", "Hello!")
        self.now += 2
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "flag_pl")
        self.assertEqual(state["elapsed"], 2)
        self.assertEqual(state["caption"], "Hello!")
        self.assertEqual(state["caption_remaining"], 6)
        self.assertEqual(state["message"], "Bottom note")
        self.assertEqual(state["message_remaining"], 28)
        self.now += 6
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["elapsed"], 0)
        self.assertIsNone(state["caption"])
        self.assertEqual(state["caption_remaining"], 0)
        self.assertEqual(state["message"], "Bottom note")
        self.assertEqual(state["message_remaining"], 22)

    def test_idle_reaction_keeps_idle_and_expires_caption_on_monotonic_deadline(self):
        self.pip.react("idle", "Still here", 4)
        self.now += 3
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["caption"], "Still here")
        self.assertEqual(state["caption_remaining"], 1)
        self.now += 1
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["elapsed"], 4)
        self.assertIsNone(state["caption"])
        self.assertEqual(state["caption_remaining"], 0)

    def test_new_reaction_replaces_caption_and_restarts_even_thinking(self):
        self.pip.react("thinking", "First", 30)
        self.now += 3
        self.pip.react("thinking", "Second", 2)
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "thinking")
        self.assertEqual(state["elapsed"], 0)
        self.assertEqual(state["caption"], "Second")
        self.assertEqual(state["caption_remaining"], 2)
        self.now += 2
        self.assertEqual(self.pip.snapshot()["state"], "idle")
        self.assertIsNone(self.pip.snapshot()["caption"])

    def test_invalid_reactions_leave_entire_live_snapshot_unchanged(self):
        self.pip.message("Keep bottom note", 60)
        self.pip.react("reading", "Keep caption", 40)
        self.now += 2
        before = self.pip.snapshot()
        cases = [
            ("unknown", "New", 8), ([], "New", 8), (None, "New", 8),
            ("smile", "", 8), ("smile", " \n ", 8), ("smile", None, 8),
            ("smile", "x" * 281, 8), ("smile", "tab\t", 8),
            ("smile", "control\x00", 8), ("smile", "New", None),
            ("smile", "New", True), ("smile", "New", "8"),
            ("smile", "New", 0), ("smile", "New", -1),
            ("smile", "New", float("nan")), ("smile", "New", float("inf")),
            ("smile", "New", 3601), ("smile", "New", 10**500),
        ]
        for mood, text, duration in cases:
            with self.subTest(mood=mood, text=text, duration=duration):
                with self.assertRaises(ValueError):
                    self.pip.react(mood, text, duration)
                self.assertEqual(self.pip.snapshot(), before)

    def test_explicit_events_and_hooks_cancel_caption_but_not_bottom_note(self):
        self.pip.message("Bottom note", 60)
        interruptions = [
            lambda: self.pip.event("idle"),
            lambda: self.pip.event("thinking"),
            lambda: self.pip.claude({"hook_event_name": "Stop"}),
            lambda: self.pip.claude({"hook_event_name": "PreToolUse"}),
        ]
        for interrupt in interruptions:
            self.pip.react("thinking", "Old reaction", 30)
            self.now += 1
            interrupt()
            state = self.pip.snapshot()
            self.assertIsNone(state["caption"])
            self.assertEqual(state["caption_remaining"], 0)
            self.assertEqual(state["message"], "Bottom note")

    def test_bottom_note_updates_do_not_replace_or_extend_reaction_caption(self):
        self.pip.react("smile", "Overhead", 4)
        self.now += 2
        self.pip.message("Updated bottom", 20)
        state = self.pip.snapshot()
        self.assertEqual(state["caption"], "Overhead")
        self.assertEqual(state["caption_remaining"], 2)
        self.now += 2
        state = self.pip.snapshot()
        self.assertIsNone(state["caption"])
        self.assertEqual(state["message"], "Updated bottom")


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = 100.0
        cls.pip = Companion(clock=lambda: cls.now)
        cls.server = create_server("127.0.0.1", 0, cls.pip, token="test-secret")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    def setUp(self):
        self.__class__.now += 4000
        self.pip.event("idle")
        self.pip.snapshot()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, payload=None, authorized=True, content_type="application/json", extra_headers=None):
        headers = {"Content-Type": content_type}
        if authorized:
            headers["Authorization"] = "Bearer test-secret"
        if extra_headers:
            headers.update(extra_headers)
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

    def test_query_reaction_decodes_unicode_newlines_and_reserved_characters_once(self):
        self.pip.message("Independent bottom", 30)
        status, body = self.request(
            "/api/react?mood=flag_aws&text=Hello%2C+%C5%81ukasz%21%0A%26%3D%2B%2520&duration=2.5")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual(state["state"], "flag_aws")
        self.assertEqual(state["elapsed"], 0)
        self.assertEqual(state["caption"], "Hello, Łukasz!\n&=+%20")
        self.assertEqual(state["caption_remaining"], 2.5)
        self.assertEqual(state["message"], "Independent bottom")
        self.assertEqual(state["message_remaining"], 30)
        self.__class__.now += 2.5
        status, body = self.request("/api/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual(state["state"], "idle")
        self.assertIsNone(state["caption"])
        self.assertEqual(state["caption_remaining"], 0)
        self.assertEqual(state["message"], "Independent bottom")


    def test_unauthorized_query_cannot_replace_any_live_state(self):
        self.pip.message("Keep bottom", 60)
        self.pip.react("reading", "Keep overhead", 40)
        before = self.pip.snapshot()
        for path in ("/api/react?mood=smile&text=Unauthorized", "/api/react?mood=smile"):
            with self.subTest(path=path):
                status, _ = self.request(path, authorized=False)
                self.assertEqual(status, 401)
                self.assertEqual(self.pip.snapshot(), before)

    def test_cross_site_or_mismatched_origin_cannot_mutate_reaction(self):
        self.pip.message("Keep bottom", 60)
        self.pip.react("reading", "Keep overhead", 40)
        before = self.pip.snapshot()
        cases = [
            {"Sec-Fetch-Site": "cross-site"},
            {"Sec-Fetch-Site": "cross-site", "Origin": self.base},
            {"Origin": "http://unrelated.example"},
            {"Origin": self.base.replace("http:", "https:")},
            {"Origin": "http://127.0.0.1:1"},
            {"Origin": "null"},
            {"Origin": self.base + "/unrelated"},
            {"Origin": self.base + "?query=1"},
            {"Origin": self.base.replace("://", "://user@")},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                status, _ = self.request("/api/react?mood=smile&text=Blocked", extra_headers=headers)
                self.assertEqual(status, 403)
                self.assertEqual(self.pip.snapshot(), before)

    def test_curl_address_bar_and_same_origin_queries_are_allowed(self):
        cases = [
            {},
            {"Sec-Fetch-Site": "none"},
            {"Sec-Fetch-Site": "same-origin", "Origin": self.base},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                status, body = self.request("/api/react?mood=idle&text=Allowed", extra_headers=headers)
                self.assertEqual(status, 200)
                state = json.loads(body)
                self.assertEqual(state["state"], "idle")
                self.assertEqual(state["caption"], "Allowed")
                self.assertEqual(state["caption_remaining"], 8)

    def test_invalid_queries_leave_animation_caption_and_bottom_note_unchanged(self):
        self.pip.message("Keep bottom", 60)
        self.pip.react("reading", "Keep overhead", 40)
        before = self.pip.snapshot()
        queries = [
            "", "mood=smile", "text=Hello", "mood=&text=Hello",
            "mood=smile&text=", "mood=smile&text=+++",
            "mood=unknown&text=Hello", "mood=smile&text=Hello&duration=",
            "mood=smile&text=Hello&duration=nan",
            "mood=smile&text=Hello&duration=inf",
            "mood=smile&text=Hello&duration=-1",
            "mood=smile&text=Hello&duration=0",
            "mood=smile&text=Hello&duration=3601",
            "mood=smile&text=Hello&duration=not-a-number",
            "mood=smile&text=Hello&token=test-secret",
            "mood=smile&text=Hello&unknown=",
            "mood=smile&mood=idle&text=Hello",
            "mood=smile&text=Hello&text=Other",
            "mood=smile&text=Hello&duration=8&duration=9",
            "mood=smile&text=Hello&%74ext=Other",
            "mood=smile&text=Hello&",
            "mood=smile&text=Hello%09", "mood=smile&text=Hello%00",
            "mood=smile&text=%FF", "mood=smile&text=%ZZ",
            "mood=smile&text=%", "mood=smile&text=" + "x" * 281,
        ]
        for query in queries:
            with self.subTest(query=query):
                status, _ = self.request("/api/react?" + query)
                self.assertEqual(status, 400)
                self.assertEqual(self.pip.snapshot(), before)

    def test_query_endpoint_requires_exact_path_and_does_not_add_post_api(self):
        self.pip.react("reading", "Keep overhead", 40)
        before = self.pip.snapshot()
        for path in ("/api/react/", "/api/react-other"):
            with self.subTest(path=path):
                status, _ = self.request(path + "?mood=smile&text=Hello")
                self.assertEqual(status, 404)
                self.assertEqual(self.pip.snapshot(), before)
        status, _ = self.request("/api/react", {"mood": "smile", "text": "Hello"})
        self.assertEqual(status, 404)
        self.assertEqual(self.pip.snapshot(), before)

    def test_existing_post_event_and_hook_interrupt_query_caption_only(self):
        self.pip.message("Keep bottom", 60)
        cases = [
            ("/api/event", {"event": "smile"}, 200, "smile"),
            ("/hooks/claude", {"hook_event_name": "Stop"}, 204, "bounce"),
        ]
        for path, payload, expected_status, expected_state in cases:
            with self.subTest(path=path):
                status, _ = self.request("/api/react?mood=thinking&text=Overhead")
                self.assertEqual(status, 200)
                status, _ = self.request(path, payload)
                self.assertEqual(status, expected_status)
                state = self.pip.snapshot()
                self.assertEqual(state["state"], expected_state)
                self.assertIsNone(state["caption"])
                self.assertEqual(state["caption_remaining"], 0)
                self.assertEqual(state["message"], "Keep bottom")

    def test_default_loopback_without_token_still_rejects_cross_site_queries(self):
        pip = Companion(clock=lambda: 100.0)
        pip.message("Bottom note", 30)
        pip.react("reading", "Keep caption", 20)
        before = pip.snapshot()
        server = create_server("127.0.0.1", 0, pip)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port) + "/api/react?mood=smile&text=Hello"
        try:
            for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://unrelated.example"}):
                with self.subTest(headers=headers):
                    request = Request(url, headers=headers)
                    with self.assertRaises(HTTPError) as result:
                        urlopen(request, timeout=3)
                    with result.exception as response:
                        self.assertEqual(response.code, 403)
                        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
                    self.assertEqual(pip.snapshot(), before)
            with urlopen(Request(url, headers={"Sec-Fetch-Site": "none"}), timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
                state = json.loads(response.read())
                self.assertEqual(state["state"], "smile")
                self.assertEqual(state["caption"], "Hello")
                self.assertEqual(state["message"], "Bottom note")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
