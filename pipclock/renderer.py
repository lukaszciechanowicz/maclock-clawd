"""Native-resolution landscape clock with bundled and custom Clawd animations."""

from __future__ import annotations

import datetime
import math
import unicodedata
from pathlib import Path

import pygame

from .animations import WebsiteAnimations
from .model import EVENT_DURATIONS


WIDTH, HEIGHT = 640, 480
PAPER = (232, 221, 198)
CREAM = (255, 252, 245)
INK = (44, 53, 47)
BLACK = (20, 20, 19)
MUTED = (125, 130, 115)
LINE = (217, 213, 197)
TEAL = (76, 112, 99)
GOLD = (210, 164, 89)
CORAL = (217, 119, 87)
ELLIPSE = tuple((math.cos(i * math.tau / 32), math.sin(i * math.tau / 32)) for i in range(32))
# Side rectangles are the arms themselves; no extra limbs are attached.
BODY = ((-72, -66), (72, -66), (72, 37), (-72, 37))
FOOT_X = (-72, -40, 24, 56)
STEP_LIFT = (0, 4, 10, 12, 8, 0, 0, 0)
STEP_SHIFT = (-4, -2, 2, 5, 4, 1, -2, -4)


class Renderer:
    """Draw a quiet 640 × 480 scene with cached artwork and header text.

    API captions take priority over timed messages, then action text, then the
    minute-only clock. Artwork keeps the same size with or without text.
    """

    def __init__(self):
        if not pygame.font.get_init():
            pygame.font.init()
        self._clock_font = pygame.font.Font(
            str(Path(__file__).with_name("assets") / "fonts" / "DSEG7Classic-Regular.ttf"), 102
        )
        unicode_path = pygame.font.match_font(
            "notosanscjksc,notosanscjk,hiraginosans,pingfangsc,arialunicode,dejavusans,arial"
        )
        self.message_fonts = {size: pygame.font.Font(unicode_path, size) for size in range(12, 33)}
        self.website = WebsiteAnimations()
        self._art_rect = pygame.Rect(0, 168, WIDTH, HEIGHT - 168)
        self._clock_key = None
        self._clock_text = None
        self._header_key = None
        self._header_surface = None
        self._wifi = self._wifi_graphics()
        self._mug = self._enlarge(self._mug_graphic(), 2)
        self._book = self._enlarge(self._book_graphic(), 2)
        self._lens = self._enlarge(self._lens_graphic(), 2)
        self._glasses = self._enlarge(self._glasses_graphic(), 2)
        morph, pulse = self._heart_graphics()
        self._heart_morph = tuple(self._enlarge(image, 2) for image in morph)
        self._heart_pulse = tuple(self._enlarge(image, 2) for image in pulse)
        self._flags = {
            state: tuple(self._enlarge(image, 1.65) for image in frames)
            for state, frames in self._flag_graphics().items()
        }

    @staticmethod
    def _enlarge(image, scale):
        return pygame.transform.scale(image, (round(image.get_width() * scale), round(image.get_height() * scale)))

    @staticmethod
    def _wifi_graphics():
        """Bake three small, distinct states; never query the host network."""
        icons = {}
        for status in ("connected", "disconnected", "unavailable"):
            image = pygame.Surface((26, 26), pygame.SRCALPHA)
            color = TEAL if status == "connected" else MUTED
            for radius in (7, 12, 17):
                pygame.draw.arc(image, color, (13 - radius, 23 - radius, radius * 2, radius * 2),
                                math.pi / 4, math.pi * 3 / 4, 2)
            pygame.draw.circle(image, color, (13, 22), 2)
            if status == "disconnected":
                pygame.draw.line(image, PAPER, (3, 3), (23, 23), 5)
                pygame.draw.line(image, INK, (3, 3), (23, 23), 2)
            elif status == "unavailable":
                pygame.draw.circle(image, PAPER, (20, 19), 6)
                pygame.draw.line(image, INK, (17, 16), (23, 22), 2)
                pygame.draw.line(image, INK, (23, 16), (17, 22), 2)
            icons[status] = image
        return icons



    @staticmethod
    def _center(surface, image, x, y):
        surface.blit(image, (round(x - image.get_width() / 2), round(y)))


    @staticmethod
    def _clusters(text):
        """Keep combining marks, variation selectors and ZWJ sequences together."""
        clusters = []
        for character in text:
            if clusters and (unicodedata.combining(character) or character in "\ufe0e\ufe0f\u200d" or clusters[-1].endswith("\u200d")):
                clusters[-1] += character
            else:
                clusters.append(character)
        return clusters

    def _wrap(self, text, font, width):
        lines = []
        for paragraph in text.split("\n"):
            current = []
            for cluster in self._clusters(paragraph):
                candidate = "".join(current) + cluster
                if current and font.size(candidate)[0] > width:
                    gap = next((i for i in range(len(current) - 1, -1, -1) if current[i].isspace()), -1)
                    if gap > 0:
                        lines.append("".join(current[:gap]).rstrip())
                        current = current[gap + 1:]
                        while current and font.size("".join(current) + cluster)[0] > width:
                            lines.append("".join(current))
                            current = []
                    else:
                        lines.append("".join(current).rstrip())
                        current = []
                if current or not cluster.isspace():
                    current.append(cluster)
            lines.append("".join(current).rstrip())
        return lines

    def _header(self, text):
        """Wrap the complete Unicode note, sharing one plain header lane."""
        if text == self._header_key:
            return self._header_surface
        clean = "".join(
            "\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else
            " " if unicodedata.category(c) == "Cc" and c != "\n" else c
            for c in text
        )
        clean = "\n".join(line for line in clean.split("\n") if line.strip()) or " "
        width, height = 576, 108
        for size in range(32, 11, -1):
            font = self.message_fonts[size]
            lines = self._wrap(clean, font, width)
            line_height = font.get_linesize()
            if len(lines) * line_height <= height and all(font.size(line)[0] <= width for line in lines):
                break
        else:
            # Excessive explicit newlines must not make 280 characters tiny.
            lines = self._wrap(" ".join(clean.split()), font, width)
        content_width = max(1, max(font.size(line)[0] for line in lines))
        content = pygame.Surface((content_width, max(1, len(lines) * line_height)), pygame.SRCALPHA)
        for index, line in enumerate(lines):
            image = font.render(line, True, INK)
            content.blit(image, ((content_width - image.get_width()) // 2, index * line_height))
        if content.get_width() > width or content.get_height() > height:
            ratio = min(width / content.get_width(), height / content.get_height())
            content = pygame.transform.smoothscale(
                content, (max(1, round(content.get_width() * ratio)), max(1, round(content.get_height() * ratio)))
            )
        rendered = pygame.Surface((width, height), pygame.SRCALPHA)
        rendered.blit(content, ((width - content.get_width()) // 2, height - content.get_height()))
        self._header_key, self._header_surface = text, rendered
        return rendered

    def _clock(self, surface, wall_time):
        key = wall_time.strftime("%H:%M")
        if key != self._clock_key:
            self._clock_text = self._clock_font.render(key, True, INK)
            self._clock_key = key
        self._center(surface, self._clock_text, 320, 54)

    @staticmethod
    def _mug_graphic():
        image = pygame.Surface((70, 62), pygame.SRCALPHA)
        # The large, square mug sits outside the left arm, like the reference.
        pygame.draw.rect(image, (113, 119, 108), (44, 17, 22, 27), 5)
        pygame.draw.rect(image, (113, 119, 108), (4, 8, 45, 46))
        pygame.draw.rect(image, (152, 155, 140), (4, 5, 45, 6))
        pygame.draw.rect(image, (89, 85, 72), (9, 5, 35, 3))
        pygame.draw.rect(image, (136, 142, 128), (4, 12, 4, 38))
        return image

    @staticmethod
    def _book_graphic():
        image = pygame.Surface((140, 76), pygame.SRCALPHA)
        def points(path):
            return [(70 + x, 2 + y) for x, y in path]
        # Only a narrow top page block faces upward toward Clawd. The large
        # panels facing the viewer are the outside covers, not printed pages.
        pygame.draw.polygon(image, CREAM, points(((-63, 6), (-10, 13), (0, 20), (10, 13), (63, 6), (63, 15), (0, 28), (-63, 15))))
        pygame.draw.lines(image, LINE, False, points(((-61, 9), (-10, 16), (0, 22), (10, 16), (61, 9))), 1)
        pygame.draw.polygon(image, TEAL, points(((-66, 13), (-10, 21), (0, 27), (0, 66), (-10, 61), (-66, 53))))
        pygame.draw.polygon(image, (58, 91, 81), points(((66, 13), (10, 21), (0, 27), (0, 66), (10, 61), (66, 53))))
        pygame.draw.lines(image, GOLD, False, points(((-62, 17), (-11, 25), (-5, 29), (-5, 59))), 1)
        pygame.draw.lines(image, GOLD, False, points(((62, 17), (11, 25), (5, 29), (5, 59))), 1)
        pygame.draw.line(image, (39, 68, 60), (70, 29), (70, 68), 3)
        pygame.draw.polygon(image, GOLD, points(((36, 30), (42, 36), (36, 42), (30, 36))), 1)
        return image

    @staticmethod
    def _lens_graphic():
        image = pygame.Surface((110, 110), pygame.SRCALPHA)
        pygame.draw.line(image, TEAL, (75, 77), (95, 98), 11)
        pygame.draw.circle(image, CREAM, (46, 46), 44)
        pygame.draw.circle(image, TEAL, (46, 46), 40)
        pygame.draw.circle(image, (229, 231, 211), (46, 46), 35)
        pygame.draw.rect(image, BLACK, (32, 28, 28, 36))
        pygame.draw.lines(image, CREAM, False, ((20, 36), (24, 26), (35, 20)), 3)
        return image

    @staticmethod
    def _glasses_graphic():
        image = pygame.Surface((190, 36), pygame.SRCALPHA)
        pygame.draw.rect(image, BLACK, (0, 0, 184, 6))
        pygame.draw.rect(image, BLACK, (184, 6, 6, 6))
        lens = ((0, 6), (78, 6), (78, 12), (72, 12), (72, 18),
                (66, 18), (66, 24), (60, 24), (60, 30), (24, 30),
                (24, 24), (18, 24), (18, 18), (12, 18), (12, 12), (6, 12), (6, 6))
        for offset in (0, 96):
            pygame.draw.polygon(image, BLACK, [(x + offset, y) for x, y in lens])
            for hx, hy in ((12, 6), (24, 6), (18, 12), (30, 12), (24, 18), (30, 24)):
                pygame.draw.rect(image, (255, 255, 255), (offset + hx, hy, 6, 6))
        return image

    @staticmethod
    def _heart_graphics():
        heart = ((0, 14), (-13, 2), (-16, -5), (-14, -11), (-8, -15), (-3, -14),
                 (0, -9), (3, -14), (8, -15), (14, -11), (16, -5), (13, 2))
        eye = ((0, 9), (-8, 9), (-8, 0), (-8, -9), (-5, -9), (-2, -9),
               (0, -9), (2, -9), (5, -9), (8, -9), (8, 0), (8, 9))
        red = (151, 47, 50)
        morph, pulse = [], []
        for index in range(10):
            amount = index / 9
            amount = amount * amount * (3 - 2 * amount)
            image = pygame.Surface((42, 42), pygame.SRCALPHA)
            color = tuple(round(a + (b - a) * amount) for a, b in zip(BLACK, red))
            path = [(round(21 + ax + (bx - ax) * amount), round(21 + ay + (by - ay) * amount))
                    for (ax, ay), (bx, by) in zip(eye, heart)]
            pygame.draw.polygon(image, color, path)
            morph.append(image)
        for index in range(16):
            image = pygame.Surface((42, 42), pygame.SRCALPHA)
            scale = 1 + math.sin(index * math.tau / 16) * 0.08
            pygame.draw.polygon(image, red, [(round(21 + x * scale), round(21 + y * scale)) for x, y in heart])
            pulse.append(image)
        return tuple(morph), tuple(pulse)

    @staticmethod
    def _flag_graphics():
        """Load official marks once and bake native-size fluttering cloth."""
        flags = {}
        brand_path = Path(__file__).with_name("assets") / "brands"
        for name in ("pl", "aws", "shipstation", "stamps"):
            polish = name == "pl"
            width, height = (128, 80) if polish else (144, 64)
            cloth = pygame.Surface((width, height), pygame.SRCALPHA)
            cloth.fill((255, 255, 255))
            if polish:
                # Poland's official 5:8 field, white above Polish crimson.
                pygame.draw.rect(cloth, (220, 20, 60), (0, height // 2, width, height // 2))
            else:
                logo = pygame.image.load(str(brand_path / (name + ".png")))
                ratio = min((width - 16) / logo.get_width(), (height - 14) / logo.get_height())
                logo = pygame.transform.smoothscale(
                    logo, (max(1, round(logo.get_width() * ratio)), max(1, round(logo.get_height() * ratio)))
                )
                cloth.blit(logo, ((width - logo.get_width()) // 2, (height - logo.get_height()) // 2))
            pygame.draw.rect(cloth, LINE, cloth.get_rect(), 1)
            strips = tuple(cloth.subsurface((column, 0, 2, height)) for column in range(0, width, 2))
            frames = []
            for index in range(24):
                phase = index * math.tau / 24
                sway = round(math.sin(phase) * (8 if polish else 1))
                heave = round(math.sin(phase) * (3 if polish else 1))
                image = pygame.Surface((190, 142), pygame.SRCALPHA)
                top = (12 + sway, 10 + heave)
                pygame.draw.lines(image, TEAL, False, (top, (12, 75), (12 - round(sway * 0.6), 128)), 4)
                pygame.draw.circle(image, GOLD, top, 3)
                for column, strip in enumerate(strips):
                    fraction = column * 2 / (width - 2)
                    flutter = round(math.sin(phase - fraction * math.tau) * fraction * (8 if polish else 2))
                    image.blit(strip, (top[0] + 2 + column * 2, top[1] + 4 + flutter))
                frames.append(image)
            flags["flag_" + name] = tuple(frames)
        return flags

    def _character(self, surface, state, t):
        # Website poses are real bundled frames; custom timing is independent.
        if self.website.draw(surface, state, t):
            return
        frame = int(t * 12)
        t = frame / 12
        x, y = 320.0, 269.0 + round(math.sin(t * 1.8))
        sx = sy = 1.0
        gaze_x, gaze_y = round(math.sin(t * 0.65)), 0
        left_top = right_top = -32
        front_left = front_right = None
        stride = False
        ringing = False
        happy = state == "smile"
        scared_phase = t % 6.8
        if state == "smile":
            y -= (0, 2, 3, 2)[(frame // 2) % 4]
        elif state == "knock":
            phase = t % 1.8
            tap = sum(math.exp(-((phase - center) / 0.09) ** 2) for center in (0.28, 0.57))
            front_right = (48 - round(tap * 3), -8 - round(tap * 3), 38 + round(tap * 6), 36 + round(tap * 6))
            gaze_x = 0
        elif state == "waiting":
            gaze_x = round(math.sin(t * 0.9) * 4)
        elif state == "coffee":
            y = 269.0
            gaze_x = gaze_y = 0
        elif state == "reading":
            gaze_x, gaze_y = round(math.sin(t * 2.2) * 3), 7
            front_left, front_right = (-83, 4, 26, 31), (57, 4, 26, 31)
        elif state == "lens":
            gaze_x = round(math.sin(t * 1.7) * 3)
            lens_x, lens_y = 48 + gaze_x, -23 + round(math.sin(t * 1.7) * 2)
            front_right = (72, -3, 29, 36)
            x += round(math.sin(t * 1.7) * 5)
        elif state == "ok":
            right_top = -64
            y += (0, 2, 4, 2)[(frame // 2) % 4]
            happy = True
        elif state == "scared":
            # Full right exit, hidden beat, opposite-edge return, brake, settle.
            if scared_phase < 0.55:
                x += (0, 3, 0, -3)[frame % 4]
                y -= round(math.sin(scared_phase / 0.55 * math.pi) * 11)
                sy = 1.05
                left_top = right_top = -62
            elif scared_phase < 2.05:
                x = 320 + 432 * (scared_phase - 0.55) / 1.5
                stride = True
            elif scared_phase < 2.8:
                return
            elif scared_phase < 4.75:
                x = -112 + 432 * (scared_phase - 2.8) / 1.95
                stride = True
            elif scared_phase < 5.45:
                brake = (scared_phase - 4.75) / 0.7
                x += round(math.sin(brake * math.pi) * 20)
            else:
                sy = 1 + math.sin((scared_phase - 5.45) * math.pi / 1.35) * 0.025
            if stride:
                y -= (0, 5, 8, 3)[frame % 4]
                left_top -= (0, 12, 24, 12)[frame % 4]
                right_top -= (24, 12, 0, 12)[frame % 4]
        elif state == "phone_ringing":
            phase = t % 3.0
            ringing = phase < 0.65 or 1.05 <= phase < 1.7
            y = 269.0
            gaze_x = 0
            if ringing:
                x += (-5, 5, -4, 4)[frame % 4]
                y += (-1, 1, 0, 1)[frame % 4]
        elif state in ("sunglasses", "deal_with_it"):
            gaze_x = 0
            y = 269.0 + (round(math.sin(t * 2) * 1.5) if state == "sunglasses" else 0)
        elif state == "closeup":
            phase = min(t, 12.0)
            if phase < 2.5:
                amount = phase / 2.5
            elif phase < 8.5:
                amount = 1.0
            else:
                amount = max(0.0, 1 - (phase - 8.5) / 2.7)
            amount = amount * amount * (3 - 2 * amount)
            sx = sy = 1 + 1.3 * amount
            # Keep the eye line centered while the body grows beyond the scene.
            y = 269 + 23 * (sy - 1)
            gaze_x = -6 if 2.5 <= phase < 4 else 6 if 4 <= phase < 5.5 else 0
            happy = 7 <= phase < 11.2
        elif state == "heart_eyes":
            gaze_x = gaze_y = 0
        elif state in self._flags:
            # The existing right-side block holds the pole; it is replaced,
            # not supplemented with a thin arm or an extra hand.
            y = 280 + round(math.sin(t * math.pi) * (3 if state == "flag_pl" else 1))
            lift = round(math.sin(t * math.pi) * (6 if state == "flag_pl" else 1))
            front_right = (68, -40 - lift, 20, 43 + lift)
            gaze_x = 2
        elif state == "cloud_engineering":
            gaze_x = gaze_y = 0
            y = 276 - round(abs(math.sin(t * math.pi * 1.5)) * 8)

        # A fixed action layout keeps props in view without breathing/jitter.
        scale = 1.65 if state in self._flags else 2.0
        center_x = 176 if state in self._flags else 320
        ground = 355 if state in self._flags else 348 if state == "cloud_engineering" else 346 if state == "ok" else 342

        def point(p):
            return (round(center_x + (x - 320 + p[0] * sx) * scale),
                    round(470 + (y - ground + p[1] * sy) * scale))

        def polygon(path, color, width=0):
            pygame.draw.polygon(surface, color, [point(p) for p in path], round(width * scale))

        def rect(box, color):
            rx, ry, rw, rh = box
            polygon(((rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)), color)

        def line(path, color=BLACK, width=3):
            pygame.draw.lines(surface, color, False, [point(p) for p in path], round(width * scale))

        def ellipse(center, rx, ry, color, width=0):
            polygon([(center[0] + a * rx, center[1] + b * ry) for a, b in ELLIPSE], color, width)

        def side_block(side, top):
            # The side rectangle IS the arm. Raised and front-facing poses
            # replace that rectangle; they never add a hand, elbow or fingers.
            inner = 56 if top < -32 else 68
            rect((inner if side > 0 else -88, top, 88 - inner, 3 - top), CORAL)

        if front_left is None:
            side_block(-1, left_top)
        if front_right is None:
            side_block(1, right_top)
        for index, foot_x in enumerate(FOOT_X):
            lift = shift = 0
            if stride:
                phase = (frame + (0, 4, 2, 6)[index]) % 8
                lift, shift = STEP_LIFT[phase], STEP_SHIFT[phase]
            elif state == "waiting" and index == 3:
                lift = (0, 0, 5, 0)[(frame // 2) % 4]
            polygon(((foot_x, 35), (foot_x + 16, 35),
                     (foot_x + 16, 58 - lift), (foot_x + 16 + shift, 58 - lift),
                     (foot_x + 16 + shift, 72 - lift), (foot_x + shift, 72 - lift),
                     (foot_x + shift, 58 - lift), (foot_x, 58 - lift)), CORAL)
        polygon(BODY, CORAL)
        blink = 4.7 < t % 5.4 < 4.9
        for eye_x in (-48, 48):
            ex, ey = eye_x + gaze_x, -23 + gaze_y
            if state in ("heart_eyes", "cloud_engineering"):
                image = self._heart_morph[frame] if frame < len(self._heart_morph) else self._heart_pulse[(frame - len(self._heart_morph)) % len(self._heart_pulse)]
                px, py = point((ex, ey))
                surface.blit(image, image.get_rect(center=(px, py)))
            elif happy:
                rect((ex - 10, ey, 6, 6), BLACK)
                rect((ex - 4, ey - 6, 10, 6), BLACK)
                rect((ex + 6, ey, 6, 6), BLACK)
            elif state == "scared" and scared_phase < 5.45:
                rect((ex - 9, ey - 13, 18, 24), BLACK)
            elif blink and state not in ("lens", "sunglasses", "deal_with_it", "closeup"):
                rect((ex - 8, ey + 2, 16, 3), BLACK)
            else:
                rect((ex - 8, ey - 9, 16, 18), BLACK)
        # Every custom face is eyes-only, including the startled and cup poses.
        if state in self._flags:
            surface.blit(self._flags[state][frame % 24], point((72, -76)))
        if front_left is not None:
            rect(front_left, CORAL)
        if front_right is not None:
            rect(front_right, CORAL)

        if state == "coffee":
            surface.blit(self._mug, point((-139, -48)))
            for index in range(2):
                line([(-123 + index * 15 + math.sin(t * 2 + step * 0.8 + index) * 2, -49 - step * 5) for step in range(5)], MUTED, 2)
        elif state == "reading":
            surface.blit(self._book, point((-70, -2)))
            page_phase = (t % 4.2 - 2.3) / 1.2
            if 0 < page_phase < 1:
                # The turning page is seen edge-on above the cover, never as
                # a printed sheet facing the viewer.
                edge = 59 * math.cos(page_phase * math.pi)
                arch = math.sin(page_phase * math.pi) * 13
                polygon(((0, 20), (edge, 6 - arch), (edge, 12 - arch), (0, 25)), CREAM)
                line(((0, 20), (edge, 6 - arch), (edge, 12 - arch)), GOLD, 1)
        elif state == "lens":
            surface.blit(self._lens, point((lens_x - 46, lens_y - 46)))
        elif state == "ok":
            line(((100, -43), (106, -37), (118, -49)), TEAL, 4)
        elif state == "knock":
            # A foreshortened block faces the front glass. Its contact face,
            # expanding rings and radial ticks replace the old side-door prop.
            for center in (0.28, 0.57):
                age = t % 1.8 - center
                if 0 <= age < 0.28:
                    radius = 25 + age * 68
                    ellipse((67, 10), radius, radius, TEAL if age < 0.14 else MUTED, 1)
                    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                        line(((67 + dx * (radius + 5), 10 + dy * (radius + 2)),
                              (67 + dx * (radius + 11), 10 + dy * (radius + 8))), GOLD, 2)
        elif state == "waiting":
            for index in range(3):
                ellipse((111 + index * 12, -45), 3, 3, TEAL if int(t * 2) % 3 == index else LINE)
            line(((-130, -37), (-108, -37), (-108, -31), (-126, -7), (-126, -1), (-108, -1), (-108, -7), (-126, -31), (-126, -37)), TEAL, 2)
            rect((-131, -40, 26, 3), TEAL)
            rect((-131, 0, 26, 3), TEAL)
            polygon(((-124, -7), (-111, -7), (-118, -17 - math.sin(t * 2) * 2)), GOLD)
            line(((-118, -23), (-118, -11)), GOLD, 1)
        elif state == "smile":
            hx, hy = -112, -47 + round(math.sin(t * 2) * 4)
            ellipse((hx - 5, hy - 3), 7, 7, CORAL)
            ellipse((hx + 5, hy - 3), 7, 7, CORAL)
            polygon(((hx - 12, hy), (hx + 12, hy), (hx, hy + 15)), CORAL)
        elif state == "scared" and 0.55 <= scared_phase < 4.75:
            for offset in range(3):
                line(((-96 - offset * 8, 18 + offset * 12), (-119 - offset * 8, 18 + offset * 12)), MUTED, 2)
        elif state == "phone_ringing" and ringing:
            for side in (-1, 1):
                for offset in (0, 12):
                    mx = side * (105 + offset + (frame % 2) * 2)
                    line(((mx, -36), (mx + side * 5, -26), (mx, -15), (mx + side * 5, -4)), TEAL, 2)
        elif state in ("sunglasses", "deal_with_it"):
            drop = 0.0
            if state == "deal_with_it":
                if t < 0.95:
                    drop = -140 * (1 - (t / 0.95) ** 2)
                elif t < 1.3:
                    drop = -8 * math.sin((t - 0.95) / 0.35 * math.pi)
            surface.blit(self._glasses, point((-90, -37 + drop)))


    def draw(
        self, surface: pygame.Surface, snapshot: dict, wall_time: datetime.datetime,
        wifi_status: str = "unavailable",
    ) -> None:
        """Draw a frame from cached network status and monotonic action time."""
        state = snapshot.get("state", "idle")
        if state not in EVENT_DURATIONS:
            state = "idle"
        elapsed = max(0.0, float(snapshot.get("elapsed", 0.0)))
        surface.fill(PAPER)
        previous_clip = surface.get_clip()
        # Protect the plain header while preserving deliberate close-up crops
        # and the scared action's complete offscreen exit/return.
        surface.set_clip(previous_clip.clip(self._art_rect))
        self._character(surface, state, elapsed)
        surface.set_clip(previous_clip)
        header = snapshot.get("caption") or snapshot.get("message")
        if not header:
            if state == "cloud_engineering":
                header = "Cloud Engineering"
            elif state == "deal_with_it" and elapsed >= 1.5:
                header = "Deal with it."
            elif state == "ok":
                header = "OK!"
        if header:
            surface.blit(self._header(str(header)), (32, 42))
        else:
            self._clock(surface, wall_time)
        surface.blit(self._wifi.get(wifi_status, self._wifi["unavailable"]), (WIDTH - 40, 14))
