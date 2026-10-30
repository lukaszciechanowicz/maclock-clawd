"""Physical button edges through gpiozero's real mock pin implementation."""

from concurrent.futures import ThreadPoolExecutor
import sys
import threading
import unittest
from unittest.mock import patch

from gpiozero import Button
from gpiozero.pins.mock import MockFactory

from pipclock.buttons import IdleButtons
from pipclock.model import Companion


class IdleButtonTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.companion = Companion(clock=lambda: self.now)
        self.companion.configure_idle(["reading", "pool", "coffee"], 5)
        self.companion.event("idle")
        self.factory = MockFactory(revision="a02082")
        self.addCleanup(self.factory.close)

    def buttons(self, previous=19, next_pin=26):
        buttons = IdleButtons.from_environment(
            self.companion,
            {"PIPCLOCK_BUTTON_PREV": str(previous), "PIPCLOCK_BUTTON_NEXT": str(next_pin)},
            pin_factory=self.factory,
        )
        self.addCleanup(buttons.close)
        return buttons

    def test_previous_and_next_pressed_edges_wrap_the_current_group(self):
        self.buttons()
        previous = self.factory.pin(19)
        next_pin = self.factory.pin(26)
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")
        next_pin.drive_high()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")
        previous.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "reading")
        previous.drive_high()
        previous.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "coffee")
        previous.drive_high()
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "reading")

    def test_repeated_low_level_and_release_do_not_step_again(self):
        self.buttons()
        next_pin = self.factory.pin(26)
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")
        pressed = self.companion.snapshot()
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot(), pressed)
        next_pin.drive_high()
        self.assertEqual(self.companion.snapshot(), pressed)
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "coffee")

    def test_press_interrupts_reaction_but_preserves_the_independent_message(self):
        self.buttons()
        configuration = self.companion.idle_config()
        self.companion.message("Bottom note", 60, text_size=96)
        self.companion.react("thinking", "Reaction caption", 20)
        self.now += 2
        self.factory.pin(26).drive_low()
        state = self.companion.snapshot()
        self.assertEqual((state["state"], state["animation"]), ("idle", "reading"))
        self.assertEqual((state["elapsed"], state["animation_elapsed"]), (0, 0))
        self.assertIsNone(state["caption"])
        self.assertEqual(state["caption_remaining"], 0)
        self.assertEqual(state["message"], "Bottom note")
        self.assertEqual(state["message_text_size"], 96)
        self.assertEqual((state["message_elapsed"], state["message_remaining"]), (2, 58))
        self.assertEqual(self.companion.idle_config(), configuration)
        self.now += 5
        self.assertEqual(self.companion.snapshot()["animation"], "pool")

    def test_press_resolves_unobserved_automatic_rotation(self):
        self.buttons()
        self.now += 11
        self.factory.pin(26).drive_low()
        state = self.companion.snapshot()
        self.assertEqual((state["state"], state["animation"]), ("idle", "reading"))
        self.assertEqual((state["elapsed"], state["animation_elapsed"]), (0, 0))
        self.now += 4
        self.assertEqual(self.companion.snapshot()["animation"], "reading")
        self.now += 1
        self.assertEqual(self.companion.snapshot()["animation"], "pool")

    def test_live_group_changes_and_single_action_groups_apply_to_buttons(self):
        self.buttons()
        self.companion.configure_idle(["kite", "coffee"], 5)
        self.factory.pin(19).drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "coffee")
        self.factory.pin(19).drive_high()
        self.companion.configure_idle(["pool"], 5)
        self.now += 16
        self.factory.pin(26).drive_low()
        state = self.companion.snapshot()
        self.assertEqual((state["state"], state["animation"], state["elapsed"]), ("idle", "pool", 0))
        self.factory.pin(19).drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")
        self.assertEqual(self.companion.idle_config(), {"actions": ["pool"], "interval": 5})

    def test_environment_can_select_the_bcm_range_boundaries(self):
        self.buttons(previous=0, next_pin=27)
        self.factory.pin(0).drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "coffee")
        self.factory.pin(27).drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "reading")

    def test_simultaneous_opposite_edges_leave_a_consistent_companion_state(self):
        self.buttons()
        barrier = threading.Barrier(2)

        def press(pin):
            barrier.wait(timeout=2)
            self.factory.pin(pin).drive_low()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(press, pin) for pin in (19, 26)]
            for future in futures:
                future.result(timeout=3)
        state = self.companion.snapshot()
        self.assertEqual((state["state"], state["animation"], state["elapsed"]), ("idle", "reading", 0))

    def test_close_disarms_both_inputs_and_preserves_the_callers_factory(self):
        other_companion = Companion(clock=lambda: self.now)
        other_companion.configure_idle(["reading", "pool"], 5)
        other_companion.event("idle")
        other_button = Button(20, pull_up=True, pin_factory=self.factory)
        self.addCleanup(other_button.close)
        other_button.when_pressed = lambda: other_companion.step_idle(1)
        buttons = self.buttons()
        previous = self.factory.pin(19)
        next_pin = self.factory.pin(26)
        before = self.companion.snapshot()
        buttons.close()
        buttons.close()
        for pin in (previous, next_pin):
            pin.drive_low()
            pin.drive_high()
        self.assertEqual(self.companion.snapshot(), before)
        self.factory.pin(20).drive_low()
        self.assertEqual(other_companion.snapshot()["animation"], "pool")
        self.buttons()
        next_pin.drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")

    def test_second_line_claim_failure_releases_first_without_stepping(self):
        blocker = Button(26, pull_up=True, pin_factory=self.factory)
        self.addCleanup(blocker.close)
        before = self.companion.snapshot()
        with self.assertRaises(RuntimeError):
            self.buttons()
        self.factory.pin(19).drive_low()
        self.assertEqual(self.companion.snapshot(), before)
        blocker.close()
        self.buttons()
        self.factory.pin(26).drive_low()
        self.assertEqual(self.companion.snapshot()["animation"], "pool")


    def test_incomplete_or_invalid_configuration_is_an_error(self):
        before = self.companion.snapshot()
        cases = [
            {"PIPCLOCK_BUTTON_PREV": "19"},
            {"PIPCLOCK_BUTTON_NEXT": "26"},
            {"PIPCLOCK_BUTTON_PREV": "19", "PIPCLOCK_BUTTON_NEXT": ""},
        ] + [
            {"PIPCLOCK_BUTTON_PREV": previous, "PIPCLOCK_BUTTON_NEXT": next_pin}
            for previous, next_pin in (("-1", "26"), ("19", "28"), ("GPIO19", "26"),
                                       ("19.0", "26"), ("19", "19"))
        ]
        for environ in cases:
            with self.subTest(environ=environ):
                with self.assertRaises(ValueError):
                    IdleButtons.from_environment(self.companion, environ, pin_factory=self.factory)
                self.assertEqual(self.companion.snapshot(), before)

    def test_enabled_configuration_reports_missing_gpio_dependencies(self):
        environ = {"PIPCLOCK_BUTTON_PREV": "19", "PIPCLOCK_BUTTON_NEXT": "26"}
        before = self.companion.snapshot()
        for missing_module in ("gpiozero", "gpiozero.pins.lgpio"):
            with self.subTest(missing_module=missing_module):
                with patch.dict(sys.modules, {missing_module: None}):
                    with self.assertRaises(RuntimeError):
                        IdleButtons.from_environment(self.companion, environ)
                self.assertEqual(self.companion.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
