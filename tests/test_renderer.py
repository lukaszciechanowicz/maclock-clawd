"""Visible clock/header precedence and unclipped character/prop layouts."""

from collections import Counter
import datetime
import unittest

import pygame

from pipclock.model import Companion
from pipclock.renderer import HEIGHT, PAPER, WIDTH, Renderer


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = Renderer()
        cls.time = datetime.datetime(2026, 10, 27, 14, 37, 12)

    def frame(self, snapshot=None, wall_time=None, wifi_status="connected"):
        surface = pygame.Surface((WIDTH, HEIGHT))
        self.renderer.draw(surface, snapshot or {"state": "idle", "elapsed": 0}, wall_time or self.time, wifi_status)
        return surface

    @staticmethod
    def pixels(surface, rectangle=None):
        return pygame.image.tobytes(surface.subsurface(rectangle) if rectangle else surface, "RGB")

    def test_clock_ignores_date_and_seconds_but_changes_with_the_minute(self):
        original = self.frame()
        same_minute = self.frame(wall_time=datetime.datetime(2031, 2, 8, 14, 37, 59))
        next_minute = self.frame(wall_time=self.time.replace(minute=38))
        self.assertEqual(self.pixels(original), self.pixels(same_minute))
        self.assertNotEqual(self.pixels(original), self.pixels(next_minute))
        self.assertEqual(self.pixels(original, (0, 168, WIDTH, 312)), self.pixels(next_minute, (0, 168, WIDTH, 312)))

    def test_caption_precedes_message_and_both_replace_the_clock_without_resizing_art(self):
        base = {"state": "idle", "elapsed": 0}
        caption = self.frame({**base, "caption": "Hello, 世界 👋"})
        both = self.frame({**base, "caption": "Hello, 世界 👋", "message": "Build complete"})
        note = self.frame({**base, "message": "Build complete"})
        later_note = self.frame({**base, "message": "Build complete"}, self.time.replace(minute=38))
        plain = self.frame(base)
        self.assertEqual(self.pixels(caption), self.pixels(both))
        self.assertEqual(self.pixels(note), self.pixels(later_note))
        self.assertNotEqual(self.pixels(note), self.pixels(caption))
        for image in (caption, note):
            self.assertEqual(self.pixels(image, (0, 168, WIDTH, 312)), self.pixels(plain, (0, 168, WIDTH, 312)))

    def test_caption_expiry_reveals_live_message_then_clock(self):
        now = [0.0]
        companion = Companion(clock=lambda: now[0])
        companion.message("Still working", 8)
        companion.react("idle", "First update", 3)
        header = (0, 0, WIDTH, 168)
        first = self.frame(companion.snapshot())
        now[0] = 4
        note = self.frame(companion.snapshot())
        expected = self.frame({"state": "idle", "message": "Still working"})
        self.assertEqual(self.pixels(note, header), self.pixels(expected, header))
        self.assertNotEqual(self.pixels(first, header), self.pixels(note, header))
        now[0] = 9
        clock = self.frame(companion.snapshot())
        self.assertEqual(self.pixels(clock, header), self.pixels(self.frame(), header))

    def test_full_unicode_note_keeps_its_last_character(self):
        prefix = "Zażółć gęślą 世界 " * 18
        prefix = (prefix + "界" * 279)[:279]
        first = self.frame({"state": "idle", "caption": prefix + "A"})
        second = self.frame({"state": "idle", "caption": prefix + "B"})
        self.assertNotEqual(self.pixels(first, (32, 42, 576, 108)), self.pixels(second, (32, 42, 576, 108)))

    def test_builtin_action_header_also_replaces_clock(self):
        for state, elapsed in (("ok", 0), ("cloud_engineering", 1), ("deal_with_it", 2)):
            with self.subTest(state=state):
                first = self.frame({"state": state, "elapsed": elapsed})
                second = self.frame({"state": state, "elapsed": elapsed}, self.time.replace(minute=38))
                self.assertEqual(self.pixels(first), self.pixels(second))

    def test_character_palette_matches_website_art_and_background_is_uniform(self):
        image = self.frame()
        website = self.frame({"state": "wave", "elapsed": 0})
        artwork = pygame.image.tobytes(website.subsurface((0, 168, WIDTH, 312)), "RGB")
        palette = Counter(zip(artwork[0::3], artwork[1::3], artwork[2::3]))
        palette.pop(PAPER, None)
        website_body = palette.most_common(1)[0][0]
        self.assertEqual(image.get_at((320, 230))[:3], website_body)
        background = image.get_at((0, 0))[:3]
        self.assertNotEqual(background, (255, 255, 255))
        for point in ((16, 16), (639, 479), (28, 380), (612, 380), (320, 479)):
            self.assertEqual(image.get_at(point)[:3], background)

    def test_ordinary_heads_feet_and_wide_props_do_not_touch_scene_edges(self):
        states = ("idle", "coffee", "reading", "lens", "ok", "flag_pl", "flag_aws", "flag_shipstation", "flag_stamps",
                  "wave", "thinking", "desktop", "blooming", "kite", "pixel_walk", "pool")
        for state in states:
            with self.subTest(state=state):
                art = self.frame({"state": state, "elapsed": 1.5}).subsurface((0, 168, WIDTH, 312)).copy()
                art.set_colorkey(PAPER)
                regions = pygame.mask.from_surface(art).get_bounding_rects()
                self.assertTrue(regions)
                bounds = regions[0].unionall(regions[1:])
                self.assertGreater(bounds.left, 0)
                self.assertLess(bounds.right, WIDTH)
                self.assertGreater(bounds.top, 0)
                self.assertLess(bounds.bottom, 312)

    def test_wifi_states_are_distinct_and_confined_to_the_corner(self):
        images = [self.frame(wifi_status=status) for status in ("connected", "disconnected", "unavailable")]
        corner = (600, 14, 26, 26)
        self.assertEqual(len({self.pixels(image, corner) for image in images}), 3)
        for image in images[1:]:
            self.assertEqual(self.pixels(image, (0, 40, WIDTH, 440)), self.pixels(images[0], (0, 40, WIDTH, 440)))


if __name__ == "__main__":
    unittest.main()
