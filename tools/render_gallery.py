"""Export every native Clawd action as a compact, looping documentation GIF.

Run on a desktop with: pip install -e '.[gallery]'
The Pi runtime does not need Pillow or these documentation assets.
"""

import argparse
from datetime import datetime
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
import pygame

from pipclock.model import EVENT_DURATIONS
from pipclock.renderer import HEIGHT, WIDTH, Renderer

FPS = 12
SIZE = (320, 240)
EXAMPLE_TIME = datetime(2026, 1, 1, 9, 41)
CUSTOM_SECONDS = {
    "idle": 6, "smile": 4, "knock": 3.6, "waiting": 6,
    "coffee": 6, "reading": 8.4, "lens": 6, "ok": 4,
    "scared": 6.8, "phone_ringing": 6, "sunglasses": 4,
    "deal_with_it": 4, "closeup": 12, "heart_eyes": 4,
    "flag_pl": 6, "flag_aws": 6, "flag_shipstation": 6,
    "flag_stamps": 6, "cloud_engineering": 6,
    "windows_bsod": 10, "windows_shutdown": 10,
}


class _PreviewGroups(HTMLParser):
    """Use the preview's categories and labels instead of a second catalog."""

    def __init__(self):
        super().__init__()
        self.groups = []
        self.heading = None
        self.event = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag == "h3":
            self.heading = []
        elif tag == "button":
            self.event = dict(attrs).get("data-event")
            self.label = []

    def handle_data(self, data):
        if self.heading is not None:
            self.heading.append(data)
        elif self.event:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "h3" and self.heading is not None:
            self.groups.append(("".join(self.heading).strip(), []))
            self.heading = None
        elif tag == "button" and self.event:
            self.groups[-1][1].append((self.event, "".join(self.label).strip()))
            self.event = None


def frame_count(event, entries):
    if event in CUSTOM_SECONDS:
        return math.ceil(CUSTOM_SECONDS[event] * FPS)
    entry = entries[event]
    if entry.get("mode") == "pingpong":
        cycle = 2 * (entry["frames"] - 1)
    elif "loop" in entry:
        cycle = entry["loop"][1] - entry["loop"][0]
    else:
        cycle = entry["frames"]
    # Keep complete source cycles, repeating short ones for at least 4 seconds.
    seconds = cycle / entry["fps"]
    return math.ceil(seconds * math.ceil(4 / seconds) * FPS)


def export_gif(renderer, surface, event, count, destination):
    frames = []
    for index in range(count):
        renderer.draw(surface, {
            "state": event, "elapsed": index / FPS,
            "message": None, "message_remaining": 0,
        }, EXAMPLE_TIME, wifi_status="connected")
        frame = Image.frombytes("RGB", (WIDTH, HEIGHT), pygame.image.tobytes(surface, "RGB"))
        frames.append(frame.resize(SIZE, Image.Resampling.NEAREST))
    # A shared palette avoids color flicker; nearest-neighbor/no dithering keeps
    # Static clock/icon pixels compress away; time and Wi-Fi are fixed examples.
    sample_indices = list(range(0, count, max(1, count // 20)))[:24]
    palette_image = Image.new("RGB", (SIZE[0] * 4, SIZE[1] * math.ceil(len(sample_indices) / 4)))
    for index, source in enumerate(sample_indices):
        palette_image.paste(frames[source], ((index % 4) * SIZE[0], (index // 4) * SIZE[1]))
    palette = palette_image.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    # GIF timing is in centiseconds: alternate 80/90 ms rather than silently
    # speeding every 12 fps animation up to 12.5 fps.
    durations = [round((i + 1) * 100 / FPS) * 10 - round(i * 100 / FPS) * 10 for i in range(count)]
    indexed[0].save(destination, save_all=True, append_images=indexed[1:],
                    duration=durations, loop=0, optimize=True, disposal=1)


def markdown(output):
    relative = Path(os.path.relpath(output, ROOT / "docs")).as_posix()
    preview = _PreviewGroups()
    preview.feed((ROOT / "pipclock" / "preview.html").read_text(encoding="utf-8"))
    events = [event for _, group in preview.groups for event, _ in group]
    if len(events) != len(set(events)) or set(events) != set(EVENT_DURATIONS):
        raise ValueError("Preview/gallery actions do not match the runtime catalog")
    lines = []
    for title, group in preview.groups:
        lines.extend((f"## {title}", "", "<table>"))
        for offset in range(0, len(group), 3):
            lines.append("  <tr>")
            for event, label in group[offset:offset + 3]:
                lines.append(f'    <td align="center" width="33%"><strong>{escape(label)}</strong><br><code>{event}</code><br><img src="{relative}/{event}.gif" alt="Animated Clawd: {escape(label, quote=True)}" width="300" height="225"></td>')
            for _ in range(3 - len(group[offset:offset + 3])):
                lines.append('    <td aria-hidden="true"></td>')
            lines.append("  </tr>")
        lines.extend(("</table>", ""))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "gallery")
    parser.add_argument("--print-markdown", action="store_true", help="print categorized three-column tables for docs/gallery.md")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    entries = json.loads((ROOT / "pipclock" / "assets" / "manifest.json").read_text())["animations"]
    renderer = Renderer()
    surface = pygame.Surface((WIDTH, HEIGHT))
    total = 0
    for event in EVENT_DURATIONS:
        count = frame_count(event, entries)
        path = args.output / (event + ".gif")
        export_gif(renderer, surface, event, count, path)
        size = path.stat().st_size
        total += size
        print(f"{event}: {count} sampled frames, {size:,} bytes", file=sys.stderr, flush=True)
    pygame.quit()
    print(f"Exported {len(EVENT_DURATIONS)} GIFs, {total:,} bytes total.", file=sys.stderr, flush=True)
    if args.print_markdown:
        print(markdown(args.output))


if __name__ == "__main__":
    main()
