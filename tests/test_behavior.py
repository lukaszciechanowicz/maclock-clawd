"""Consumer-visible timer, hook and HTTP security boundaries."""

from collections import Counter
import json
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipclock.model import Companion, EVENT_DURATIONS
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

    def test_text_sizes_and_scroll_clocks_are_independent_of_actions_and_each_other(self):
        self.pip.configure_idle(["idle", "pool"], 5)
        self.pip.message("First note", 30, text_size=32)
        self.now += 2
        self.pip.react("idle", "Caption", 20, text_size=96)
        self.now += 6
        state = self.pip.snapshot()
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["animation"], "pool")
        self.assertEqual(state["message_text_size"], 32)
        self.assertEqual(state["message_elapsed"], 8)
        self.assertEqual(state["caption_text_size"], 96)
        self.assertEqual(state["caption_elapsed"], 6)
        self.pip.message("Replacement", 30)
        state = self.pip.snapshot()
        self.assertEqual(state["message_elapsed"], 0)
        self.assertEqual(state["caption_elapsed"], 6)
        self.assertEqual(state["animation_elapsed"], 1)
        self.pip.event("thinking", 20)
        self.now += 3
        self.assertEqual(self.pip.snapshot()["message_elapsed"], 3)
        self.pip.react("thinking", "Replacement caption", 8)
        self.assertEqual(self.pip.snapshot()["caption_elapsed"], 0)

    def test_invalid_text_sizes_leave_all_state_unchanged(self):
        self.pip.message("Keep note", 30, text_size=96)
        self.pip.react("reading", "Keep caption", 20, text_size=32)
        self.now += 2
        before = self.pip.snapshot()
        for size in (31, 97, 64.0, 64.5, True, False, None, "64", [], 10**500):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    self.pip.message("New note", 10, text_size=size)
                self.assertEqual(self.pip.snapshot(), before)
                with self.assertRaises(ValueError):
                    self.pip.react("idle", "New caption", 10, text_size=size)
                self.assertEqual(self.pip.snapshot(), before)


class IdleTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pip = Companion(clock=lambda: self.now)


    def test_idle_rotation_accounts_for_unobserved_intervals(self):
        self.pip.configure_idle(["reading", "pool", "coffee"], 5)
        self.pip.event("idle")
        self.now += 5 * 3 * 1000000 + 6
        state = self.pip.snapshot()
        self.assertEqual((state["state"], state["animation"], state["animation_elapsed"]),
                         ("idle", "pool", 1))

    def test_interruption_and_hook_resume_restart_playlist_at_event_deadline(self):
        self.pip.configure_idle(["pool", "reading", "kite"], 5)
        self.pip.event("idle")
        self.now += 6
        self.assertEqual(self.pip.snapshot()["animation"], "reading")
        self.pip.event("smile", 4)
        self.now += 2
        state = self.pip.snapshot()
        self.assertEqual((state["state"], state["animation"], state["elapsed"], state["animation_elapsed"]),
                         ("smile", "smile", 2, 2))
        self.now += 8
        state = self.pip.snapshot()
        self.assertEqual((state["state"], state["animation"], state["elapsed"], state["animation_elapsed"]),
                         ("idle", "reading", 6, 1))
        self.pip.claude({"hook_event_name": "Stop"})
        self.now += 8
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.now += 6
        self.pip.claude({"hook_event_name": "SessionEnd"})
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["elapsed"], state["animation_elapsed"]), ("pool", 0, 0))

    def test_config_changes_preserve_live_event_and_caption_but_restart_idle(self):
        self.pip.message("Note", 100)
        self.pip.react("reading", "Caption", 10)
        self.now += 3
        before = self.pip.snapshot()
        self.pip.configure_idle(["kite", "pool"], 5)
        self.assertEqual(self.pip.snapshot(), before)
        self.now += 8
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"]), ("kite", 1))
        self.pip.react("idle", "Idle caption", 20, text_size=96)
        self.now += 6
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.pip.configure_idle(["reading", "coffee"], 5)
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"], state["elapsed"]), ("reading", 0, 0))
        self.assertEqual((state["caption"], state["caption_elapsed"], state["caption_text_size"]),
                         ("Idle caption", 6, 96))
        self.assertEqual(state["message_elapsed"], 17)

    def test_change_after_unobserved_expiry_and_single_action_are_continuous(self):
        self.pip.event("smile", 2)
        self.now += 20
        self.pip.configure_idle(["pool"], 5)
        state = self.pip.snapshot()
        self.assertEqual((state["state"], state["animation"], state["elapsed"]), ("idle", "pool", 0))
        self.now += 123
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"], state["elapsed"]), ("pool", 123, 123))

    def test_all_catalog_actions_and_interval_boundaries_are_supported(self):
        actions = list(EVENT_DURATIONS)
        for interval in (5, 5.5, 3600):
            with self.subTest(interval=interval):
                self.pip.configure_idle(actions, interval)
                self.assertEqual(self.pip.idle_config(), {"actions": actions, "interval": interval})
        actions.clear()
        returned = self.pip.idle_config()
        returned["actions"].clear()
        self.assertEqual(self.pip.idle_config()["actions"], list(EVENT_DURATIONS))

    def test_invalid_configuration_preserves_config_event_text_and_timing(self):
        self.pip.event("idle")
        self.pip.message("Note", 30, text_size=96)
        self.pip.react("idle", "Caption", 20, text_size=32)
        self.now += 6
        before = self.pip.snapshot()
        config = self.pip.idle_config()
        cases = [
            (None, 30), ([], 30), ("idle", 30), (("idle",), 30),
            (["idle", "idle"], 30), (["unknown"], 30), (["bored"], 30),
            ([None], 30), ([[]], 30), ([True], 30),
        ] + [(["pool"], value) for value in
             (None, True, False, "30", 0, 4.99, 3600.01, float("nan"), float("inf"), -float("inf"), 10**500)]
        for actions, interval in cases:
            with self.subTest(actions=actions, interval=interval):
                with self.assertRaises(ValueError):
                    self.pip.configure_idle(actions, interval)
                self.assertEqual(self.pip.idle_config(), config)
                self.assertEqual(self.pip.snapshot(), before)


class WeightedIdleTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pip = Companion(clock=lambda: self.now)

    def test_retro_scenes_appear_once_per_ten_appearances_of_each_normal_pose(self):
        groups = [
            (["reading", "windows_bsod", "coffee", "windows_shutdown"],
             {"reading": 10, "coffee": 10, "windows_bsod": 1, "windows_shutdown": 1}),
            (["windows_shutdown", "reading", "windows_bsod"],
             {"reading": 10, "windows_bsod": 1, "windows_shutdown": 1}),
            (["coffee", "windows_bsod"], {"coffee": 10, "windows_bsod": 1}),
        ]
        for actions, expected in groups:
            with self.subTest(actions=actions):
                self.pip.configure_idle(actions, 5)
                self.pip.event("idle")
                start = self.now
                sequence = []
                for turn in range(sum(expected.values())):
                    self.now = start + turn * 5
                    state = self.pip.snapshot()
                    self.assertEqual(state["state"], "idle")
                    sequence.append(state["animation"])
                self.assertEqual(sequence[0], actions[0])
                self.assertEqual(Counter(sequence), expected)
                self.now = start + sum(expected.values()) * 5 * 1000000
                self.assertEqual(self.pip.snapshot()["animation"], actions[0])
                self.assertEqual(self.pip.idle_config()["actions"], actions)

    def test_manual_steps_select_rare_entries_immediately_in_configured_order(self):
        actions = ["reading", "windows_bsod", "coffee", "windows_shutdown"]
        self.pip.configure_idle(actions, 5)
        self.pip.event("idle")
        for expected in actions[1:] + actions[:1]:
            self.pip.step_idle(1)
            state = self.pip.snapshot()
            self.assertEqual((state["animation"], state["animation_elapsed"]), (expected, 0))
        self.pip.step_idle(-1)
        self.assertEqual(self.pip.snapshot()["animation"], "windows_shutdown")
        self.now += 4.5
        self.assertEqual(self.pip.snapshot()["animation"], "windows_shutdown")
        self.now += 0.5
        self.assertEqual(self.pip.snapshot()["animation"], "reading")

    def test_retro_only_and_single_retro_groups_remain_usable(self):
        self.pip.configure_idle(["windows_bsod", "windows_shutdown"], 5)
        self.pip.event("idle")
        self.now += 5
        self.assertEqual(self.pip.snapshot()["animation"], "windows_shutdown")
        self.now += 5
        self.assertEqual(self.pip.snapshot()["animation"], "windows_bsod")
        self.pip.configure_idle(["windows_shutdown"], 5)
        self.now += 27.5
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"]), ("windows_shutdown", 27.5))

    def test_failed_persistence_does_not_replace_the_weighted_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            pip = Companion(clock=lambda: self.now, idle_config_path=Path(directory) / "idle.json")
            config = {"actions": ["reading", "windows_bsod", "coffee", "windows_shutdown"], "interval": 5}
            pip.configure_idle(**config)
            pip.event("idle")
            pip.step_idle(1)
            before = pip.snapshot()
            with patch("pipclock.model.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    pip.configure_idle(["coffee"], 5)
            self.assertEqual(pip.snapshot(), before)
            self.assertEqual(pip.idle_config(), config)
            self.now += 5
            self.assertEqual(pip.snapshot()["animation"], "coffee")


class ManualIdleTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pip = Companion(clock=lambda: self.now)
        self.pip.configure_idle(["pool", "reading", "coffee"], 5)
        self.pip.event("idle")

    def test_previous_and_next_wrap_the_configured_list(self):
        for direction, expected in ((-1, "coffee"), (1, "pool"), (1, "reading"),
                                    (1, "coffee"), (1, "pool"), (-1, "coffee")):
            with self.subTest(direction=direction, expected=expected):
                self.pip.step_idle(direction)
                state = self.pip.snapshot()
                self.assertEqual((state["state"], state["animation"], state["animation_elapsed"]),
                                 ("idle", expected, 0))

    def test_step_uses_current_automatic_pose_and_restarts_its_timer(self):
        self.now += 6.5
        self.pip.step_idle(1)
        self.assertEqual(self.pip.snapshot()["animation"], "coffee")
        self.now += 4.5
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"]), ("coffee", 4.5))
        self.now += 0.5
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"]), ("pool", 0))
        self.now += 5 * 3 * 1000000 + 6
        self.pip.step_idle(-1)
        self.assertEqual(self.pip.snapshot()["animation"], "pool")

    def test_step_interrupts_caption_but_preserves_independent_message(self):
        self.pip.message("Keep scrolling", 60, text_size=80)
        self.now += 2
        self.pip.react("reading", "Action caption", 20, text_size=96)
        self.now += 4
        self.pip.step_idle(1)
        state = self.pip.snapshot()
        self.assertEqual((state["state"], state["animation"]), ("idle", "coffee"))
        self.assertIsNone(state["caption"])
        self.assertEqual(state["caption_remaining"], 0)
        self.assertEqual((state["message"], state["message_text_size"], state["message_elapsed"],
                          state["message_remaining"]), ("Keep scrolling", 80, 6, 54))
        self.pip.event("wave", 20)
        self.pip.step_idle(1)
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.pip.event("wave", 20)
        self.pip.step_idle(-1)
        self.assertEqual(self.pip.snapshot()["animation"], "coffee")

    def test_explicit_events_expiry_and_reconfiguration_reset_manual_selection(self):
        self.pip.step_idle(-1)
        self.pip.event("idle")
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.pip.step_idle(1)
        self.pip.react("idle", "Caption", 20)
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.pip.step_idle(-1)
        self.pip.event("wave", 2)
        self.now += 2
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.pip.step_idle(1)
        self.pip.configure_idle(["sleeping", "headphones"], 10)
        self.assertEqual(self.pip.snapshot()["animation"], "sleeping")
        self.now += 10
        self.assertEqual(self.pip.snapshot()["animation"], "headphones")

    def test_single_entry_remains_continuous_and_invalid_steps_do_not_mutate(self):
        self.pip.configure_idle(["pool"], 5)
        self.now += 27
        self.pip.step_idle(-1)
        self.now += 6
        state = self.pip.snapshot()
        self.assertEqual((state["animation"], state["animation_elapsed"]), ("pool", 6))
        before = self.pip.snapshot()
        for direction in (0, 2, -2, True, False, 1.0, "1", None):
            with self.subTest(direction=direction):
                with self.assertRaises(ValueError):
                    self.pip.step_idle(direction)
                self.assertEqual(self.pip.snapshot(), before)

    def test_manual_selection_never_rewrites_the_saved_playlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idle.json"
            pip = Companion(clock=lambda: self.now, idle_config_path=path)
            config = {"actions": ["pool", "reading"], "interval": 5}
            pip.configure_idle(**config)
            saved = path.read_bytes()
            pip.event("idle")
            for direction in (1, -1, -1):
                pip.step_idle(direction)
            self.assertEqual(path.read_bytes(), saved)
            self.assertEqual(pip.idle_config(), config)
            restarted = Companion(clock=lambda: self.now, idle_config_path=path)
            restarted.event("idle")
            self.assertEqual(restarted.snapshot()["animation"], "pool")


class IdlePersistenceTests(unittest.TestCase):
    def test_missing_config_defaults_then_atomic_private_save_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "idle.json"
            pip = Companion(idle_config_path=path)
            self.assertFalse(path.exists())
            config = {"actions": ["pool", "kite"], "interval": 5.5}
            self.assertEqual(pip.configure_idle(**config), config)
            self.assertEqual(json.loads(path.read_text()), config)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            restarted = Companion(idle_config_path=path)
            self.assertEqual(restarted.idle_config(), config)
            restarted.event("idle")
            self.assertEqual(restarted.snapshot()["animation"], "pool")

    def test_invalid_stored_config_is_a_clear_startup_failure(self):
        values = [
            b"{", b"\xff", b"[]", b"{}", b'{"actions": ["unknown"], "interval": 30}',
            b'{"actions": ["pool", "pool"], "interval": 30}',
            b'{"actions": ["pool"], "interval": true}',
            b'{"actions": ["pool"], "interval": NaN}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idle.json"
            for value in values:
                with self.subTest(value=value):
                    path.write_bytes(value)
                    with self.assertRaises(ValueError):
                        Companion(idle_config_path=path)

    def test_save_failure_does_not_publish_or_change_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idle.json"
            pip = Companion(clock=lambda: 100.0, idle_config_path=path)
            pip.configure_idle(["pool", "kite"], 5)
            pip.react("idle", "Keep caption", 20)
            before, config, stored = pip.snapshot(), pip.idle_config(), path.read_bytes()
            with patch("pipclock.model.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    pip.configure_idle(["reading"], 30)
            self.assertEqual(pip.snapshot(), before)
            self.assertEqual(pip.idle_config(), config)
            self.assertEqual(path.read_bytes(), stored)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = 100.0
        cls.pip = Companion(clock=lambda: cls.now)
        cls.default_idle_config = cls.pip.idle_config()
        cls.server = create_server("127.0.0.1", 0, cls.pip, token="test-secret")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    def setUp(self):
        self.__class__.now += 4000
        self.pip.event("idle")
        self.pip.configure_idle(**self.default_idle_config)
        self.pip.snapshot()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, payload=None, authorized=True, content_type="application/json", extra_headers=None, base=None):
        headers = {"Content-Type": content_type}
        if authorized:
            headers["Authorization"] = "Bearer test-secret"
        if extra_headers:
            headers.update(extra_headers)
        body = None if payload is None else json.dumps(payload).encode()
        request = Request((self.base if base is None else base) + path, data=body, headers=headers)
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_retro_event_and_caption_requests_bypass_rarity_and_honor_duration(self):
        for event in ("windows_bsod", "windows_shutdown"):
            with self.subTest(event=event):
                status, body = self.request("/api/event", {"event": event, "duration": 12})
                self.assertEqual(status, 200)
                state = json.loads(body)
                self.assertEqual((state["state"], state["animation"]), (event, event))
                self.__class__.now += 11.5
                self.assertEqual(self.pip.snapshot()["state"], event)
                self.__class__.now += 0.5
                self.assertEqual(self.pip.snapshot()["state"], "idle")
                status, body = self.request("/api/react?mood=" + event + "&text=Hello&duration=4&text_size=80")
                self.assertEqual(status, 200)
                state = json.loads(body)
                self.assertEqual((state["animation"], state["caption"], state["caption_remaining"]),
                                 (event, "Hello", 4))
                self.__class__.now += 4
                state = self.pip.snapshot()
                self.assertEqual(state["state"], "idle")
                self.assertIsNone(state["caption"])

    def test_message_and_reaction_text_sizes_and_independent_clocks(self):
        status, body = self.request("/api/message", {"text": "Note", "duration": 30, "text_size": 32})
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual((state["message_text_size"], state["message_elapsed"]), (32, 0))
        self.__class__.now += 2
        status, body = self.request("/api/react?mood=idle&text=Caption&duration=20&text_size=96")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual((state["caption_text_size"], state["caption_elapsed"]), (96, 0))
        self.assertEqual(state["message_elapsed"], 2)
        self.__class__.now += 3
        status, body = self.request("/api/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual((state["message_elapsed"], state["caption_elapsed"]), (5, 3))

    def test_invalid_json_text_sizes_do_not_mutate_live_state(self):
        self.pip.message("Keep note", 60, text_size=96)
        self.pip.react("reading", "Keep caption", 40, text_size=32)
        before = self.pip.snapshot()
        for size in (31, 97, 64.0, 64.5, True, False, None, "64", [], 10**500):
            with self.subTest(size=size):
                status, _ = self.request("/api/message", {"text": "New", "duration": 10, "text_size": size})
                self.assertEqual(status, 400)
                self.assertEqual(self.pip.snapshot(), before)

    def test_idle_configuration_is_authenticated_and_updates_visible_playlist(self):
        before, config = self.pip.snapshot(), self.pip.idle_config()
        for payload in (None, {"actions": ["pool"], "interval": 5}):
            with self.subTest(payload=payload):
                status, _ = self.request("/api/idle", payload, authorized=False)
                self.assertEqual(status, 401)
                self.assertEqual(self.pip.idle_config(), config)
                self.assertEqual(self.pip.snapshot(), before)
        status, body = self.request("/api/idle")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), config)
        new_config = {"actions": ["pool", "reading"], "interval": 5.5}
        status, body = self.request("/api/idle", new_config)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), new_config)
        self.assertEqual(self.pip.snapshot()["animation"], "pool")
        self.__class__.now += 6
        status, body = self.request("/api/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual((state["state"], state["animation"], state["animation_elapsed"]), ("idle", "reading", 0.5))
        status, body = self.request("/api/idle")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), new_config)

    def test_invalid_idle_posts_preserve_config_and_all_live_state(self):
        self.pip.react("reading", "Keep caption", 40)
        self.pip.message("Keep note", 60)
        before, config = self.pip.snapshot(), self.pip.idle_config()
        values = [
            {}, {"actions": ["pool"]}, {"interval": 5}, [],
            {"actions": [], "interval": 5},
            {"actions": ["pool", "pool"], "interval": 5},
            {"actions": ["unknown"], "interval": 5},
            {"actions": "pool", "interval": 5},
            {"actions": [None], "interval": 5},
        ] + [{"actions": ["pool"], "interval": value} for value in
             (None, True, False, "5", 4.99, 3600.01, float("nan"), float("inf"), -float("inf"))]
        cases = [(payload, "application/json", 400) for payload in values]
        cases.extend([
            ({"actions": ["pool"], "interval": 5}, "text/plain", 415),
            ({"actions": ["pool"], "interval": 5, "padding": "x" * 16384}, "application/json", 413),
        ])
        for payload, content_type, expected in cases:
            with self.subTest(payload=payload, content_type=content_type):
                status, _ = self.request("/api/idle", payload, content_type=content_type)
                self.assertEqual(status, expected)
                self.assertEqual(self.pip.idle_config(), config)
                self.assertEqual(self.pip.snapshot(), before)

    def test_idle_http_persistence_and_save_failure_are_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "idle.json"
            pip = Companion(clock=lambda: 100.0, idle_config_path=path)
            server = create_server("127.0.0.1", 0, pip, token="test-secret")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "http://127.0.0.1:" + str(server.server_port)
            try:
                config = {"actions": ["pool", "kite"], "interval": 5}
                status, body = self.request("/api/idle", config, base=base)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), config)
                self.assertEqual(Companion(idle_config_path=path).idle_config(), config)
                pip.react("idle", "Keep caption", 20)
                before, stored = pip.snapshot(), path.read_bytes()
                for error in (OSError("disk failure"), TimeoutError("save timed out")):
                    with self.subTest(error=type(error).__name__):
                        with patch("pipclock.model.os.replace", side_effect=error):
                            status, body = self.request("/api/idle", {"actions": ["reading"], "interval": 30}, base=base)
                        self.assertEqual(status, 500)
                        self.assertIn("persist", json.loads(body)["error"])
                        self.assertEqual(pip.snapshot(), before)
                        self.assertEqual(pip.idle_config(), config)
                        self.assertEqual(path.read_bytes(), stored)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

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
            "mood=smile&text=Hello&text_size=",
            "mood=smile&text=Hello&text_size=31",
            "mood=smile&text=Hello&text_size=97",
            "mood=smile&text=Hello&text_size=true",
            "mood=smile&text=Hello&text_size=64.0",
            "mood=smile&text=Hello&text_size=6e1",
            "mood=smile&text=Hello&text_size=+64",
            "mood=smile&text=Hello&text_size=64%20",
            "mood=smile&text=Hello&text_size=64&text_size=96",
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
