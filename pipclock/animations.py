"""Offline playback of baked website art, with one decoded atlas in memory."""

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
        self._rectangles = ()

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
            self._rectangles = ()
            return False
        if state != self._event:
            self._atlas = None
            image = pygame.image.load(self._directory / entry["file"])
            self._atlas = image.convert_alpha() if pygame.display.get_surface() is not None else image
            width, height = entry["frame_size"]
            columns = entry["columns"]
            self._rectangles = tuple(
                pygame.Rect((index % columns) * width, (index // columns) * height, width, height)
                for index in range(entry["frames"])
            )
            self._event = state
        frame = self.frame_index(entry, elapsed)
        offset_x, offset_y = entry["offset"]
        surface.blit(self._atlas, (320 + offset_x, 343 + offset_y), self._rectangles[frame])
        return True
