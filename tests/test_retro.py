"""Pixel-level retro artwork, one-shot peek, and readable API text behavior."""

from collections import Counter
import datetime
import unittest

import pygame

from pipclock.model import Companion
from pipclock.renderer import BLACK, CORAL, HEIGHT, WIDTH, Renderer


class RetroRendererTests(unittest.TestCase):
    scenes = ("windows_bsod", "windows_shutdown")

    @classmethod
    def setUpClass(cls):
        cls.renderer = Renderer()
        cls.time = datetime.datetime(2026, 10, 27, 14, 37, 12)
        cls.font_path = pygame.font.match_font(
            "notosanscjksc,notosanscjk,hiraginosans,pingfangsc,arialunicode,dejavusans,arial"
        )

    def frame(self, state, elapsed=0, wall_time=None, wifi_status="connected", **snapshot):
        surface = pygame.Surface((WIDTH, HEIGHT))
        self.renderer.draw(
            surface, {"state": state, "elapsed": elapsed, **snapshot}, wall_time or self.time, wifi_status
        )
        return surface

    @staticmethod
    def pixels(image, rectangle=None):
        return pygame.image.tobytes(image.subsurface(rectangle) if rectangle else image, "RGB")

    @classmethod
    def changes(cls, before, after, rectangle=None):
        area = pygame.Rect(rectangle or (0, 0, WIDTH, HEIGHT))
        original = cls.pixels(before, area)
        updated = cls.pixels(after, area)
        return [
            (area.x + index % area.width, area.y + index // area.width)
            for index, (a, b) in enumerate(zip(zip(*[iter(original)] * 3), zip(*[iter(updated)] * 3)))
            if a != b
        ]

    @staticmethod
    def bounds(points):
        xs, ys = zip(*points)
        return pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)

    @staticmethod
    def contrast(first, second):
        def luminance(color):
            channels = [value / 255 for value in color]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                      for value in channels]
            return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
        light, dark = sorted((luminance(first), luminance(second)), reverse=True)
        return (light + 0.05) / (dark + 0.05)

    def test_peek_is_delayed_partial_centered_and_never_repeats(self):
        for state in self.scenes:
            with self.subTest(state=state):
                baseline = self.frame(state)
                for elapsed in (0, 2.99, 3, 8, 10, 23, 104):
                    self.assertEqual(self.pixels(self.frame(state, elapsed)), self.pixels(baseline))
                for elapsed in (3.25, 3.5, 4, 5.8, 7, 7.5, 7.75):
                    image = self.frame(state, elapsed)
                    points = self.changes(baseline, image)
                    self.assertTrue(points)
                    bounds = self.bounds(points)
                    self.assertGreaterEqual(bounds.width, WIDTH // 5)
                    self.assertLessEqual(bounds.width, WIDTH // 3)
                    self.assertEqual(bounds.centerx, WIDTH // 2)
                    self.assertEqual(bounds.bottom, HEIGHT)
                    self.assertGreaterEqual(bounds.top, HEIGHT - 80)
                    self.assertLessEqual(bounds.height, 80)
                    colors = Counter(image.get_at(point)[:3] for point in points)
                    self.assertGreater(colors[CORAL], len(points) * 0.8)
                    self.assertTrue(set(colors).issubset({CORAL, BLACK}))
                full = self.bounds(self.changes(baseline, self.frame(state, 4)))
                self.assertGreaterEqual(full.height, 50)

    def test_rise_and_sink_are_smooth_symmetric_and_continuous_at_boundaries(self):
        baseline = self.frame("windows_bsod")
        heights = []
        for elapsed in (3, 3.1, 3.25, 3.5, 3.75, 3.9, 4):
            rising = self.frame("windows_bsod", elapsed)
            sinking = self.frame("windows_bsod", 11 - elapsed)
            points = self.changes(baseline, rising)
            heights.append(self.bounds(points).height if points else 0)
            self.assertEqual(self.pixels(rising), self.pixels(sinking))
        self.assertEqual(heights, sorted(heights))
        self.assertLess(heights[1], 5)
        self.assertGreater(heights[-2], 65)
        for boundary in (3, 4, 7, 8):
            before = self.frame("windows_bsod", boundary - 0.001)
            after = self.frame("windows_bsod", boundary + 0.001)
            self.assertEqual(self.pixels(before), self.pixels(after))

    def test_visible_head_has_two_block_eyes_that_look_and_blink(self):
        neutral = self.frame("windows_shutdown", 4)
        left = self.frame("windows_shutdown", 4.3)
        right = self.frame("windows_shutdown", 5.8)
        blink = self.frame("windows_shutdown", 4.75)
        eye_area = pygame.Rect(240, 440, 160, 30)

        def eyes(image):
            return [(x, y) for y in range(eye_area.top, eye_area.bottom)
                    for x in range(eye_area.left, eye_area.right) if image.get_at((x, y))[:3] == BLACK]

        neutral_eyes, left_eyes, right_eyes, closed_eyes = map(eyes, (neutral, left, right, blink))
        self.assertTrue(neutral_eyes)
        self.assertLess(len(closed_eyes), len(neutral_eyes) / 3)
        self.assertLess(self.bounds(left_eyes).centerx, self.bounds(neutral_eyes).centerx)
        self.assertGreater(self.bounds(right_eyes).centerx, self.bounds(neutral_eyes).centerx)
        self.assertEqual(self.bounds(left_eyes).size, self.bounds(right_eyes).size)
        self.assertTrue(any(x < WIDTH // 2 for x, _ in neutral_eyes))
        self.assertTrue(any(x > WIDTH // 2 for x, _ in neutral_eyes))
        self.assertFalse(any(abs(x - WIDTH // 2) < 20 for x, _ in neutral_eyes))
        for image in (left, right, blink):
            changed = self.changes(neutral, image)
            self.assertTrue(all(eye_area.collidepoint(point) for point in changed))

    def test_animation_selection_time_controls_idle_and_button_peeks(self):
        for state in self.scenes:
            for elapsed in (0, 3.5, 4.75, 5.8, 7.5, 12):
                with self.subTest(state=state, elapsed=elapsed):
                    direct = self.frame(state, elapsed)
                    idle = self.frame("idle", 537, animation=state, animation_elapsed=elapsed)
                    self.assertEqual(self.pixels(idle), self.pixels(direct))

    def test_manual_next_and_previous_start_a_fresh_visible_selection(self):
        now = [0.0]
        companion = Companion(clock=lambda: now[0])
        companion.configure_idle(["idle", *self.scenes], 20)
        now[0] = 11
        companion.step_idle(1)
        self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(self.scenes[0])))
        now[0] = 16
        self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(self.scenes[0], 5)))
        companion.step_idle(1)
        self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(self.scenes[1])))
        now[0] = 21
        self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(self.scenes[1], 5)))
        companion.step_idle(-1)
        self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(self.scenes[0])))

    def test_replayed_explicit_event_restarts_the_one_shot_peek(self):
        for state in self.scenes:
            with self.subTest(state=state):
                now = [0.0]
                companion = Companion(clock=lambda: now[0])
                companion.event(state, duration=20)
                now[0] = 5.8
                visible = self.frame(**companion.snapshot())
                self.assertNotEqual(self.pixels(visible), self.pixels(self.frame(state)))
                now[0] = 10
                self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(state)))
                companion.event(state, duration=20)
                self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(self.frame(state)))
                now[0] = 15.8
                self.assertEqual(self.pixels(self.frame(**companion.snapshot())), self.pixels(visible))

    def test_clock_is_absent_but_wifi_remains_live_and_localized(self):
        for state in self.scenes:
            baseline = self.frame(state)
            self.assertEqual(self.pixels(baseline), self.pixels(self.frame(state, wall_time=self.time.replace(minute=38))))
            images = [self.frame(state, wifi_status=status) for status in ("connected", "disconnected", "unavailable")]
            self.assertEqual(len({self.pixels(image, (600, 14, 26, 26)) for image in images}), 3)
            for image in images[1:]:
                self.assertTrue(all(pygame.Rect(600, 14, 26, 26).collidepoint(point)
                                    for point in self.changes(baseline, image)))

    def test_same_api_text_stays_legible_when_switching_scene_and_back(self):
        # Reuse identical text and size across scenes to exercise glyph color changes.
        normal = self.frame("idle", message="Hgj")
        for state in self.scenes:
            with self.subTest(state=state):
                baseline = self.frame(state)
                image = self.frame(state, message="Hgj")
                changes = self.changes(baseline, image)
                self.assertTrue(changes)
                self.assertTrue(all(pygame.Rect(32, 42, 576, 120).collidepoint(point) for point in changes))
                color = Counter(image.get_at(point)[:3] for point in changes).most_common(1)[0][0]
                background = baseline.get_at((320, 100))[:3]
                self.assertGreaterEqual(self.contrast(color, background), 4.5)
                self.assertEqual(self.pixels(self.frame("idle", message="Hgj")), self.pixels(normal))

    def test_caption_precedes_message_with_its_own_size_and_scroll_time(self):
        text = "Caption movement must use its own clock, never the retro animation clock."
        for state in self.scenes:
            with self.subTest(state=state):
                both = self.frame(state, 4.3, caption=text, caption_text_size=96, caption_elapsed=3,
                                  message="Hidden", message_text_size=32, message_elapsed=9)
                caption = self.frame(state, 4.3, caption=text, caption_text_size=96, caption_elapsed=3)
                message = self.frame(state, 4.3, message=text, message_text_size=96, message_elapsed=3)
                self.assertEqual(self.pixels(both), self.pixels(caption))
                self.assertEqual(self.pixels(both), self.pixels(message))
                later = self.frame(state, 9, caption=text, caption_text_size=96, caption_elapsed=3)
                self.assertEqual(self.pixels(both, (32, 42, 576, 120)), self.pixels(later, (32, 42, 576, 120)))
                moving = self.frame(state, 4.3, caption=text, caption_text_size=96, caption_elapsed=4)
                self.assertNotEqual(self.pixels(both, (32, 42, 576, 120)), self.pixels(moving, (32, 42, 576, 120)))
                self.assertEqual(self.pixels(both, (0, 168, WIDTH, 312)), self.pixels(self.frame(state, 4.3), (0, 168, WIDTH, 312)))

    def test_requested_text_size_and_centering_are_preserved_over_artwork(self):
        for state in self.scenes:
            for size in (32, 64, 96):
                with self.subTest(state=state, size=size):
                    baseline = self.frame(state)
                    image = self.frame(state, message="Hgj", message_text_size=size)
                    changes = self.changes(baseline, image)
                    color = Counter(image.get_at(point)[:3] for point in changes).most_common(1)[0][0]
                    glyphs = pygame.font.Font(self.font_path, size).render("Hgj", True, color)
                    expected = baseline.copy()
                    expected.blit(glyphs, (320 - glyphs.get_width() // 2, 102 - glyphs.get_height() // 2))
                    self.assertEqual(self.pixels(image), self.pixels(expected))


if __name__ == "__main__":
    unittest.main()
