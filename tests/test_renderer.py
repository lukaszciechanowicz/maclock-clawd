"""Visible clock/header precedence and unclipped character/prop layouts."""

from collections import Counter
import datetime
import unittest

import pygame

from pipclock.model import Companion
from pipclock.renderer import HEIGHT, INK, PAPER, WIDTH, Renderer


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = Renderer()
        cls.time = datetime.datetime(2026, 10, 27, 14, 37, 12)
        cls.unicode_font = pygame.font.match_font(
            "notosanscjksc,notosanscjk,hiraginosans,pingfangsc,arialunicode,dejavusans,arial"
        )
        cls.header = (32, 42, 576, 120)

    def frame(self, snapshot=None, wall_time=None, wifi_status="connected"):
        surface = pygame.Surface((WIDTH, HEIGHT))
        self.renderer.draw(surface, snapshot or {"state": "idle", "elapsed": 0}, wall_time or self.time, wifi_status)
        return surface

    @staticmethod
    def pixels(surface, rectangle=None):
        return pygame.image.tobytes(surface.subsurface(rectangle) if rectangle else surface, "RGB")

    def glyphs(self, text, size=64):
        return pygame.font.Font(self.unicode_font, size).render(text, True, INK)

    def expected_header(self, glyphs, *positions):
        lane = pygame.Surface((576, 120))
        lane.fill(PAPER)
        y = 60 - glyphs.get_height() // 2
        for x in positions or (288 - glyphs.get_width() // 2,):
            lane.blit(glyphs, (x, y))
        return self.pixels(lane)

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

    def test_requested_sizes_are_drawn_without_resizing(self):
        for size in range(32, 97):
            with self.subTest(size=size):
                glyphs = self.glyphs("Hgj", size)
                for kind in ("message", "caption"):
                    image = self.frame({kind: "Hgj", kind + "_text_size": size})
                    self.assertEqual(self.pixels(image, self.header), self.expected_header(glyphs))

    def test_short_text_stays_centered_while_long_text_enters_and_moves_left(self):
        for kind in ("message", "caption"):
            with self.subTest(kind=kind):
                short = {kind: "Hello", kind + "_text_size": 96}
                first = self.frame({**short, kind + "_elapsed": 0})
                later = self.frame({**short, kind + "_elapsed": 83})
                self.assertEqual(self.pixels(first, self.header), self.pixels(later, self.header))
                self.assertEqual(
                    self.pixels(first, self.header), self.expected_header(self.glyphs("Hello", 96))
                )
                text = "A much longer single line to read without shrinking or wrapping."
                long = {kind: text}
                glyphs = self.glyphs(text)
                blank = pygame.Surface((576, 120))
                blank.fill(PAPER)
                initial = self.frame({**long, kind + "_elapsed": 0})
                self.assertEqual(self.pixels(initial, self.header), self.pixels(blank))
                for elapsed in (1, 2):
                    moving = self.frame({**long, kind + "_elapsed": elapsed})
                    self.assertEqual(
                        self.pixels(moving, self.header),
                        self.expected_header(glyphs, 576 - elapsed * 100),
                    )
                self.assertNotEqual(
                    self.pixels(self.frame({**long, kind + "_elapsed": 1}), self.header),
                    self.pixels(self.frame({**long, kind + "_elapsed": 2}), self.header),
                )

    def test_long_unicode_tail_and_combining_marks_scroll_into_view(self):
        prefix = ("Zażółć gęślą 世界 " * 18)[:277]
        text = prefix + "A\u0301Z"
        glyphs = self.glyphs(text)
        # Put the final 240 pixels in the lane, after the first line's leading
        # text has left. No character-count truncation may discard the tail.
        distance = glyphs.get_width() + 336
        image = self.frame({"caption": text, "caption_elapsed": distance / 100})
        x = 576 - distance
        self.assertEqual(
            self.pixels(image, self.header),
            self.expected_header(glyphs, x, x + glyphs.get_width() + 64),
        )
        different = self.frame({"caption": prefix + "B\u0301Z", "caption_elapsed": distance / 100})
        self.assertNotEqual(self.pixels(image, self.header), self.pixels(different, self.header))

    def test_ticker_repeats_with_a_64_pixel_gap_and_clips_before_art_and_wifi(self):
        text = "Readable text with a predictable gap between each repeated line."
        glyphs = self.glyphs(text, 96)
        distance = glyphs.get_width() + 96
        snapshot = {"message": text, "message_text_size": 96, "message_elapsed": distance / 100}
        image = self.frame(snapshot)
        x = 576 - distance
        self.assertEqual(
            self.pixels(image, self.header),
            self.expected_header(glyphs, x, x + glyphs.get_width() + 64),
        )
        baseline = self.frame({"message": "Hi"})
        self.assertEqual(self.pixels(image, (0, 168, WIDTH, 312)), self.pixels(baseline, (0, 168, WIDTH, 312)))
        self.assertEqual(self.pixels(image, (600, 14, 26, 26)), self.pixels(baseline, (600, 14, 26, 26)))
        for rectangle in ((0, 40, 32, 128), (608, 40, 32, 128), (0, 162, WIDTH, 6)):
            self.assertEqual(self.pixels(image, rectangle), self.pixels(baseline, rectangle))

    def test_newlines_flatten_and_lone_surrogates_do_not_discard_unicode(self):
        image = self.frame({"message": "A\u0301\nB\ud800", "message_text_size": 96})
        expected = self.frame({"message": "A\u0301 B\ufffd", "message_text_size": 96})
        self.assertEqual(self.pixels(image), self.pixels(expected))

    def test_caption_precedence_uses_its_own_size_and_scroll_clock(self):
        text = "Caption scroll position is independent of the background action."
        snapshot = {
            "state": "idle", "elapsed": 91, "animation": "coffee", "animation_elapsed": 2,
            "caption": text, "caption_text_size": 96, "caption_elapsed": 3,
            "message": "Hidden message", "message_text_size": 32, "message_elapsed": 9,
        }
        first = self.frame(snapshot)
        later = self.frame({
            **snapshot, "elapsed": 152, "animation": "pool", "animation_elapsed": 17,
            "message_elapsed": 45,
        }, self.time.replace(minute=38))
        expected = self.frame({"caption": text, "caption_text_size": 96, "caption_elapsed": 3})
        self.assertEqual(self.pixels(first, self.header), self.pixels(expected, self.header))
        self.assertEqual(self.pixels(first, self.header), self.pixels(later, self.header))
        message = self.frame({
            **snapshot, "caption": None, "message": text, "message_elapsed": 3, "message_text_size": 96,
        })
        self.assertEqual(self.pixels(first, self.header), self.pixels(message, self.header))

    def test_message_scroll_clock_survives_idle_pose_and_action_changes(self):
        snapshot = {
            "state": "idle", "elapsed": 50, "animation": "reading", "animation_elapsed": 4,
            "message": "An independent message clock keeps this ticker moving continuously.",
            "message_elapsed": 2,
        }
        first = self.frame(snapshot)
        for changes in (
            {"animation": "pool", "animation_elapsed": 0, "elapsed": 60},
            {"state": "wave", "animation": "wave", "animation_elapsed": 1, "elapsed": 1},
        ):
            image = self.frame({**snapshot, **changes})
            self.assertEqual(self.pixels(first, self.header), self.pixels(image, self.header))

    def test_idle_dispatch_uses_visible_pose_and_its_animation_time(self):
        art = (0, 168, WIDTH, 312)
        for state in ("pool", "reading", "coffee", "wave"):
            with self.subTest(state=state):
                idle = self.frame({"state": "idle", "elapsed": 94, "animation": state, "animation_elapsed": 1.5})
                explicit = self.frame({"state": state, "elapsed": 1.5})
                self.assertEqual(self.pixels(idle, art), self.pixels(explicit, art))
                self.assertNotEqual(self.pixels(idle, art), self.pixels(self.frame(), art))
        idle_builtin = self.frame({
            "state": "idle", "elapsed": 94, "animation": "deal_with_it", "animation_elapsed": 0.5,
        })
        explicit_builtin = self.frame({"state": "deal_with_it", "elapsed": 0.5})
        self.assertEqual(self.pixels(idle_builtin), self.pixels(explicit_builtin))

    def test_builtin_action_headers_replace_clock(self):
        for state, elapsed in (
            ("ok", 0),
            ("cloud_engineering", 1),
            ("deal_with_it", 2),
        ):
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
