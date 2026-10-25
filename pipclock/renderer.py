"""Native-resolution landscape clock with bundled and custom Clawd animations."""

from __future__ import annotations

import datetime
import math
import unicodedata

import pygame

from .animations import WebsiteAnimations
from .catalog import WEBSITE_ACTIONS


WIDTH, HEIGHT = 640, 480
PAPER = (246, 241, 230)
CREAM = (255, 252, 245)
SCENE = (241, 235, 222)
INK = (44, 53, 47)
BLACK = (21, 23, 21)
MUTED = (125, 130, 115)
LINE = (217, 213, 197)
TEAL = (76, 112, 99)
GOLD = (210, 164, 89)
CORAL = (199, 123, 96)
SHADOW = (219, 210, 191)
ELLIPSE = tuple((math.cos(i * math.tau / 32), math.sin(i * math.tau / 32)) for i in range(32))
# Side rectangles are the arms themselves; no extra limbs are attached.
BODY = ((-72, -66), (72, -66), (72, 37), (-72, 37))
FOOT_X = (-72, -40, 24, 56)
STEP_LIFT = (0, 4, 10, 12, 8, 0, 0, 0)
STEP_SHIFT = (-4, -2, 2, 5, 4, 1, -2, -4)
STATUS = {
    "idle": ("READY WHEN YOU ARE", "A little company.", "A quiet desk. A good place to begin."),
    "wave": ("NICE TO SEE YOU", "Oh, hello there!", "Make yourself at home."),
    "thinking": ("CONNECTING THE DOTS", "A thought is taking shape...", "Good ideas deserve a little room."),
    "bounce": ("A LITTLE EXTRA ENERGY", "Small joys. Big bounce.", "A spring in all four steps."),
    "dance": ("DESK-SIZED DISCO", "Found my rhythm.", "No dance floor required."),
    "smile": ("THE BRIGHT SIDE", "You're doing a lovely job.", "Just thought you should know."),
    "knock": ("KNOCK, KNOCK", "Anyone home?", "A tiny knock. A friendly visitor."),
    "waiting": ("TAKE YOUR TIME", "No rush. I'm here.", "A little pause can be a good thing."),
    "sleeping": ("QUIET HOURS", "Recharging the good vibes.", "Shh... just a little desk nap."),
    "coffee": ("ONE GOOD COFFEE", "A well-earned little break.", "A warm mug and a quiet moment."),
    "reading": ("JUST ONE MORE PAGE", "Lost in a good book.", "A whole adventure, right here on the desk."),
    "lens": ("A CLOSER LOOK", "Something interesting here...", "A little theatrical desk detective."),
    "ok": ("LOOKING GOOD", "All OK over here!", "You've got this. Every little bit of it."),
    "scared": ("A SMALL STARTLE", "Oh! Just passing through!", "Off to the right. Back from the left. Safe again."),
    "phone_ringing": ("A LITTLE BUZZ", "Someone's calling!", "A silent ring. A desk-sized vibration."),
    "sunglasses": ("LOOKING SHARP", "Keeping it pixel cool.", "Classic shades. Quiet confidence."),
    "deal_with_it": ("STAY COOL", "Cool under pressure.", "A little confidence, right on cue."),
    "closeup": ("UP CLOSE", "A friendly closer look.", "Just two eyes and a little smile."),
    "heart_eyes": ("ALL HEART", "A little love for your day.", "Two tiny hearts. One happy companion."),
}


for _state, _action in WEBSITE_ACTIONS.items():
    STATUS.setdefault(_state, (_action["label"].upper(), _action["label"] + ".", "Website animation from claude.dev."))


class Renderer:
    """Draw onto a logical 640 × 480 surface without creating a display.

    Background, fonts, labels, clock and the most recent message are cached.
    Character motion uses native-size primitives, never supersampled frames.
    """

    def __init__(self):
        if not pygame.font.get_init():
            pygame.font.init()
        self.fonts = {size: pygame.font.Font(None, size) for size in (14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 38, 96)}
        unicode_path = pygame.font.match_font(
            "notosanscjksc,notosanscjk,hiraginosans,pingfangsc,arialunicode,dejavusans,arial"
        )
        self.message_fonts = {size: pygame.font.Font(unicode_path, size) for size in range(12, 25)}
        self.website = WebsiteAnimations()
        self.background = self._background()
        self.status_text = {
            state: (self._text(eyebrow, 16, TEAL), self._fit_label(title, 32, 550), self._text(subtitle, 18, MUTED))
            for state, (eyebrow, title, subtitle) in STATUS.items()
        }
        self._clock_key = None
        self._clock_text = ()
        self._message_key = None
        self._message_surface = None
        self._message_label = self._text("A NOTE FOR YOU", 16, TEAL)
        self._ok_text = self._text("OK!", 24, TEAL)
        self._tap_text = self._text("tap tap", 16, TEAL)
        self._deal_text = self._text("Deal with it.", 26, INK)
        self._mug = self._mug_graphic()
        self._book = self._book_graphic()
        self._lens = self._lens_graphic()
        self._glasses = self._glasses_graphic()
        self._heart_morph, self._heart_pulse = self._heart_graphics()

    def _text(self, text, size, color=INK):
        return self.fonts[size].render(text, True, color)

    def _fit_label(self, text, size, width):
        for candidate in sorted((s for s in self.fonts if s <= size), reverse=True):
            if self.fonts[candidate].size(text)[0] <= width:
                return self._text(text, candidate)
        return self._text(text, 14)

    @staticmethod
    def _center(surface, image, x, y):
        surface.blit(image, (round(x - image.get_width() / 2), round(y)))

    def _background(self):
        surface = pygame.Surface((WIDTH, HEIGHT))
        surface.fill(PAPER)
        pygame.draw.rect(surface, INK, (12, 12, 616, 456), 2, border_radius=19)
        pygame.draw.rect(surface, LINE, (17, 17, 606, 446), 1, border_radius=15)
        pygame.draw.rect(surface, CORAL, (32, 27, 70, 23), border_radius=5)
        self._center(surface, self._text("CLAWD", 20, CREAM), 67, 31)
        surface.blit(self._text("YOUR LITTLE DESK COMPANION", 16, TEAL), (114, 33))
        pygame.draw.circle(surface, TEAL, (600, 39), 4)
        pygame.draw.line(surface, LINE, (349, 65), (349, 130))
        pygame.draw.rect(surface, SCENE, (24, 151, 592, 209), border_radius=9)
        for x in range(41, 611, 22):
            for y in range(169, 340, 22):
                pygame.draw.circle(surface, (226, 220, 204), (x, y), 1)
        pygame.draw.rect(surface, (232, 224, 207), (25, 349, 590, 10))
        pygame.draw.line(surface, (205, 197, 176), (25, 349), (615, 349))
        surface.blit(self._text("A LITTLE SPACE TO BE YOURSELF", 14, MUTED), (36, 161))
        surface.blit(self._text("100% GOOD COMPANY", 14, MUTED), (472, 337))
        pygame.draw.rect(surface, SHADOW, (29, 375, 584, 83), border_radius=11)
        pygame.draw.rect(surface, CREAM, (27, 372, 586, 83), border_radius=11)
        pygame.draw.rect(surface, LINE, (27, 372, 586, 83), 1, border_radius=11)
        return surface

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

    def _message(self, message):
        if message == self._message_key:
            return self._message_surface
        # Reject neither Unicode notes nor JSON's possible lone surrogates.
        clean = "".join(
            "\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else
            " " if unicodedata.category(c) == "Cc" and c != "\n" else c
            for c in message
        )
        clean = "\n".join(line for line in clean.split("\n") if line.strip()) or " "
        width, height = 550, 55
        for size in range(24, 11, -1):
            font = self.message_fonts[size]
            lines = self._wrap(clean, font, width)
            line_height = font.get_linesize()
            if len(lines) * line_height <= height and all(font.size(line)[0] <= width for line in lines):
                break
        else:
            clean = " ".join(clean.split())
            for size in range(24, 11, -1):
                font = self.message_fonts[size]
                lines = self._wrap(clean, font, width)
                line_height = font.get_linesize()
                if len(lines) * line_height <= height:
                    break
        rendered = pygame.Surface((width, height), pygame.SRCALPHA)
        total_height = len(lines) * line_height
        content = pygame.Surface((max(width, max((font.size(line)[0] for line in lines), default=1)), max(1, total_height)), pygame.SRCALPHA)
        for index, line in enumerate(lines):
            image = font.render(line, True, INK)
            content.blit(image, ((content.get_width() - image.get_width()) // 2, index * line_height))
        # Only a changed, exceptionally dense note is scaled, never a frame.
        if content.get_width() > width or content.get_height() > height:
            ratio = min(width / content.get_width(), height / content.get_height())
            content = pygame.transform.smoothscale(content, (max(1, round(content.get_width() * ratio)), max(1, round(content.get_height() * ratio))))
        rendered.blit(content, ((width - content.get_width()) // 2, (height - content.get_height()) // 2))
        self._message_key, self._message_surface = message, rendered
        return rendered

    def _clock(self, surface, wall_time):
        key = wall_time.strftime("%Y-%m-%d %H:%M:%S")
        if key != self._clock_key:
            self._clock_text = (
                self._text(wall_time.strftime("%H:%M"), 96),
                self._text(wall_time.strftime("%S"), 34, TEAL),
                self._fit_label(wall_time.strftime("%A").upper(), 24, 235),
                self._fit_label(wall_time.strftime("%d %B %Y"), 22, 235),
                self._text("LOCAL TIME", 14, MUTED),
            )
            self._clock_key = key
        clock, seconds, day, date, label = self._clock_text
        surface.blit(clock, (32, 60))
        surface.blit(seconds, (284, 92))
        surface.blit(label, (279, 76))
        surface.blit(day, (371, 74))
        surface.blit(date, (371, 103))

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
        tap = 0.0
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
            sx = sy = 1 + 3.6 * amount
            # Keep the eye line centered while the body grows beyond the scene.
            y = 269 + 23 * (sy - 1)
            gaze_x = -6 if 2.5 <= phase < 4 else 6 if 4 <= phase < 5.5 else 0
            happy = 7 <= phase < 11.2
        elif state == "heart_eyes":
            gaze_x = gaze_y = 0

        def point(p):
            return round(x + p[0] * sx), round(y + p[1] * sy)

        def polygon(path, color, width=0):
            pygame.draw.polygon(surface, color, [point(p) for p in path], width)

        def rect(box, color):
            rx, ry, rw, rh = box
            polygon(((rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)), color)

        def line(path, color=BLACK, width=3):
            pygame.draw.lines(surface, color, False, [point(p) for p in path], width)

        def ellipse(center, rx, ry, color, width=0):
            polygon([(center[0] + a * rx, center[1] + b * ry) for a, b in ELLIPSE], color, width)

        def side_block(side, top):
            # The side rectangle IS the arm. Raised and front-facing poses
            # replace that rectangle; they never add a hand, elbow or fingers.
            inner = 56 if top < -32 else 68
            rect((inner if side > 0 else -88, top, 88 - inner, 3 - top), CORAL)

        shadow_width = round(135 - max(0, 269 - y) * 0.9)
        pygame.draw.ellipse(surface, SHADOW, (round(x - shadow_width / 2), 342, shadow_width, 10))
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
            if state == "heart_eyes":
                image = self._heart_morph[frame] if frame < len(self._heart_morph) else self._heart_pulse[(frame - len(self._heart_morph)) % len(self._heart_pulse)]
                px, py = point((ex, ey))
                surface.blit(image, (px - 21, py - 21))
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
            bx, by = point((-132, -67))
            pygame.draw.rect(surface, CREAM, (bx - 9, by - 5, 55, 32), border_radius=4)
            surface.blit(self._ok_text, (bx, by))
            line(((100, -43), (106, -37), (118, -49)), TEAL, 4)
        elif state == "knock":
            # A foreshortened block faces the front glass. Its contact face,
            # expanding rings and radial ticks replace the old side-door prop.
            fx, fy, fw, fh = front_right
            rect((fx, fy, 4, fh), (170, 96, 77))
            rect((fx + 5, fy + 3, fw - 9, 3), (220, 148, 117))
            for center in (0.28, 0.57):
                age = t % 1.8 - center
                if 0 <= age < 0.28:
                    radius = 25 + age * 68
                    ellipse((67, 10), radius, radius, TEAL if age < 0.14 else MUTED, 1)
                    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                        line(((67 + dx * (radius + 5), 10 + dy * (radius + 2)),
                              (67 + dx * (radius + 11), 10 + dy * (radius + 8))), GOLD, 2)
            if tap > 0.2:
                surface.blit(self._tap_text, point((109, -28)))
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
                if t >= 1.5:
                    self._center(surface, self._deal_text, 320, 176)
            surface.blit(self._glasses, point((-90, -37 + drop)))


    def draw(self, surface: pygame.Surface, snapshot: dict, wall_time: datetime.datetime) -> None:
        """Render a complete frame; only snapshot elapsed time drives the action."""
        state = snapshot.get("state", "idle")
        if state not in STATUS:
            state = "idle"
        elapsed = max(0.0, float(snapshot.get("elapsed", 0.0)))
        surface.blit(self.background, (0, 0))
        self._clock(surface, wall_time)
        # Moving Clawd goes behind the scene's window/bezel, never over the clock
        # or the note. The scared route also passes beyond the full 640 px width.
        previous_clip = surface.get_clip()
        surface.set_clip(previous_clip.clip(pygame.Rect(26, 153, 588, 205)))
        self._character(surface, state, elapsed)
        surface.set_clip(previous_clip)
        pygame.draw.rect(surface, LINE, (24, 151, 592, 209), 2, border_radius=9)
        message = snapshot.get("message")
        if message:
            self._center(surface, self._message_label, 320, 380)
            surface.blit(self._message(str(message)), (45, 397))
        else:
            eyebrow, title, subtitle = self.status_text[state]
            self._center(surface, eyebrow, 320, 382)
            self._center(surface, title, 320, 403)
            self._center(surface, subtitle, 320, 435)
