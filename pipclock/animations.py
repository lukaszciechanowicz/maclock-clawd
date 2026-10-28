"""Offline website artwork with one decoded atlas and one enlarged frame."""

import json
from pathlib import Path

import pygame

from .catalog import WEBSITE_ACTIONS


class WebsiteAnimations:
    def __init__(self):
        self._directory = Path(__file__).with_name("assets")
        manifest = json.loads((self._directory / "manifest.json").read_text())
        self._animations = manifest["animations"]
        if set(self._animations) != set(WEBSITE_ACTIONS):
            raise ValueError("Bundled Clawd animation catalog is incomplete; run tools/bake_clawd.py")
        self._event = None
        self._atlas = None
        self._frames = ()
        self._frame_number = None
        self._scaled = None
        self._position = (0, 0)

    @staticmethod
    def frame_index(entry, elapsed):
        count = entry["frames"]
        tick = int(max(0, elapsed) * entry["fps"])
        if entry.get("mode") == "pingpong" and count > 1:
            position = tick % (2 * (count - 1))
            return position if position < count else 2 * (count - 1) - position
        if "loop" in entry:
            start, end = entry["loop"]
            return start + tick % (end - start)
        return tick % count

    def draw(self, surface, state, elapsed):
        entry = self._animations.get(state)
        if entry is None:
            # Release a large website atlas when returning to procedural art.
            self._event = None
            self._atlas = None
            self._frames = ()
            self._frame_number = None
            self._scaled = None
            return False
        if state != self._event:
            self._frames = ()
            self._atlas = None
            image = pygame.image.load(self._directory / entry["file"])
            self._atlas = image.convert_alpha() if pygame.display.get_surface() is not None else image
            width, height = entry["frame_size"]
            columns = entry["columns"]
            self._frames = tuple(
                self._atlas.subsurface(((index % columns) * width, (index // columns) * height, width, height))
                for index in range(entry["frames"])
            )
            # The atlas frame is the union of every pose, not today's bounding
            # box. Fit once per action so jumping, flags and props cannot jitter.
            scale = min(2.4, 592 / width, 292 / (height - 2))
            size = (round(width * scale), round(height * scale))
            # transform.scale copies pixel values without converting channel masks.
            self._scaled = pygame.Surface(
                size, pygame.SRCALPHA, self._atlas.get_bitsize(), self._atlas.get_masks()
            )
            offset_x, offset_y = entry["offset"]
            self._position = (
                max(24, min(616 - size[0], round(320 + offset_x * scale))),
                round(470 + offset_y * scale),
            )
            self._frame_number = None
            self._event = state
        frame = self.frame_index(entry, elapsed)
        if frame != self._frame_number:
            pygame.transform.scale(self._frames[frame], self._scaled.get_size(), self._scaled)
            self._frame_number = frame
        surface.blit(self._scaled, self._position)
        return True
