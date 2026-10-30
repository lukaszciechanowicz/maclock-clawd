"""Native SDL display loop. Browser mirroring is explicitly opt-in."""

import argparse
from datetime import datetime
import io
import ipaddress
import os
import signal
import threading
import time

from .buttons import IdleButtons
from .model import Companion
from .network import WifiMonitor
from .server import Frames, create_server


def main():
    parser = argparse.ArgumentParser(description="Clawd, your tiny landscape desk companion")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument(
        "--rotation", type=int, choices=(0, 90, 180, 270), default=0,
        help="rotate the physical display counterclockwise; preview stays landscape",
    )
    parser.add_argument("--preview", action="store_true", help="enable the local browser mirror")
    parser.add_argument("--headless", action="store_true", help="mirror only; requires --preview")
    args = parser.parse_args()
    if not 1 <= args.fps <= 60:
        parser.error("--fps must be between 1 and 60")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        loopback = ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        parser.error("--host must be a numeric IP address")
    # The shipped server uses IPv4; make unsupported addresses explicit.
    if ":" in args.host:
        parser.error("--host must be an IPv4 address")
    token = os.environ.get("PIPCLOCK_TOKEN")
    if not loopback and not token:
        parser.error("set PIPCLOCK_TOKEN before exposing the API outside loopback")
    if args.preview and not loopback:
        parser.error("--preview is local-only; bind to a loopback address")
    if args.headless and not args.preview:
        parser.error("--headless requires --preview")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from .renderer import HEIGHT, WIDTH, Renderer

    pygame.display.init()
    pygame.font.init()
    server = None
    buttons = None
    try:
        flags = pygame.FULLSCREEN if args.fullscreen else 0
        display_size = (HEIGHT, WIDTH) if args.rotation in (90, 270) else (WIDTH, HEIGHT)
        screen = pygame.display.set_mode(display_size, flags)
        if args.fullscreen and not args.headless and screen.get_size() != display_size:
            actual_width, actual_height = screen.get_size()
            parser.error(
                f"fullscreen display is {actual_width}x{actual_height}, "
                f"but --rotation {args.rotation} requires {display_size[0]}x{display_size[1]}; "
                "choose a rotation matching the panel dimensions"
            )
        canvas = pygame.Surface((WIDTH, HEIGHT)).convert() if args.rotation else screen
        pygame.display.set_caption("Clawd — a little desktop company")
        pygame.mouse.set_visible(not args.fullscreen)
        companion = Companion(idle_config_path=os.environ.get("PIPCLOCK_IDLE_CONFIG"))
        try:
            buttons = IdleButtons.from_environment(companion)
        except (ValueError, RuntimeError) as error:
            parser.error(str(error))
        if buttons is not None:
            print(
                f"Clawd GPIO buttons: previous BCM {buttons.previous_pin}, next BCM {buttons.next_pin}",
                flush=True,
            )
        renderer = Renderer()
        wifi = WifiMonitor()
        frames = Frames() if args.preview else None
        server = create_server(args.host, args.port, companion, frames, token)
        thread = threading.Thread(target=server.serve_forever, name="pip-http", daemon=True)
        thread.start()
        print(f"Clawd is listening at http://{args.host}:{args.port}", flush=True)
        print("Tap Clawd to knock. Escape or close the window to quit.", flush=True)
        if args.preview:
            print(f"Live preview: http://{args.host}:{args.port}/", flush=True)
        running = True

        def stop(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        ticker = pygame.time.Clock()
        next_mirror = 0
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    companion.event("knock")
            renderer.draw(canvas, companion.snapshot(), datetime.now(), wifi_status=wifi.status())
            if args.rotation:
                screen.blit(pygame.transform.rotate(canvas, args.rotation), (0, 0))
            pygame.display.flip()
            now = time.monotonic()
            if frames is not None and now >= next_mirror:
                buffer = io.BytesIO()
                pygame.image.save(canvas, buffer, "frame.jpg")
                frames.put(buffer.getvalue())
                next_mirror = now + 1 / 12
            ticker.tick(args.fps)
    finally:
        try:
            if buttons is not None:
                buttons.close()
        finally:
            try:
                if server is not None:
                    server.shutdown()
                    server.server_close()
            finally:
                pygame.quit()


if __name__ == "__main__":
    main()
