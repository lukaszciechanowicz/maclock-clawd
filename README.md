# Maclock Clawd: a desk companion

An animated Clawd and calculator-style clock for a **640 × 480 landscape screen**. Built for a Raspberry Pi Zero W inside a Maclock enclosure, with a Mac preview for trying all 64 reactions before touching the hardware.

**Some of the animations are my own custom creations, made specifically for this project. Other animations use the animation library from [claude.dev](https://claude.dev/). That library was the inspiration for this project's animation style and Clawd's movement.**

## Quick start on Mac

From the repository root, with Python 3.12 installed:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m pipclock --headless --preview
```

Open **<http://127.0.0.1:8765/>**. Try individual reactions, play the full catalog, send a timed note, or pair a reaction with text above Clawd.

Keep the process running; stop it with Ctrl-C. If the browser reports `ERR_CONNECTION_REFUSED`, start the command above before reloading. For a native window instead, run `.venv/bin/python -m pipclock --preview`; closing that window also stops the server.

## Physical previous/next buttons

The native service supports two normally-open buttons: **previous on BCM GPIO19 (physical pin 35)** and **next on BCM GPIO26 (physical pin 37)**, both switching to **GND (pin 39)**. Each press steps through the configured idle playlist, wrapping at either end and restarting the automatic-rotation timer. It interrupts an active reaction and clears its caption without restarting or discarding an independent timed message.

The Pi service enables these pins by default; desktop runs leave GPIO disabled unless both `PIPCLOCK_BUTTON_PREV` and `PIPCLOCK_BUTTON_NEXT` are set. See the [wiring, dependencies and enable/disable runbook](docs/raspberry-pi.md#optional-physical-previousnext-buttons) before connecting switches. No additional daemon, HTTP endpoint or SSH session is needed for button operation.

## Development tests

Install the test extra for the full suite, including hardware-independent GPIO edge tests:

```sh
.venv/bin/pip install -e '.[test]'
SDL_VIDEODRIVER=dummy .venv/bin/python -m unittest discover -s tests -v
```

The normal desktop install above remains pygame-only; it does not require GPIO libraries when buttons are disabled.

## Documentation

| Guide | Contents |
| --- | --- |
| [Animation gallery](docs/gallery.md) | All 64 animated GIFs, grouped like the preview and arranged three per row. |
| [API cookbook and reference](docs/api.md) | Copy/paste LAN curl and Python examples, text sizes/scrolling, idle configuration, authentication and all 64 reactions. |
| [Raspberry Pi configuration and operations](docs/raspberry-pi.md) | Recorded SD/boot, display, USB/SSH, locale and package changes; native service, secrets, deployment, backups and troubleshooting. |
| [Claude Code integration](docs/claude-code.md) | Opt-in lifecycle hooks, event mappings and secure connections. |
| [Artwork and attribution](docs/artwork.md) | Source credits, rights notices and rebuilding the animations/gallery. |

## How it works

- Python and pygame render natively; the Pi needs no browser, LLM or runtime animation downloads.
- Custom block-shaped poses sit alongside bundled frames from claude.dev. The side rectangles are Clawd's arms.
- Normal scenes show a larger, consistently terracotta Clawd near the bottom of a flat sand background; no frame, date, slogans or lower status panel. The two retro Windows scenes instead use user-provided fullscreen backgrounds and one small delayed Clawd peek.
- The raised calculator-style clock uses bundled DSEG7 Classic digits and shows only hours and minutes. API captions and timed messages replace it above Clawd without shrinking the artwork; reaction captions take priority over timed messages. Retro scenes omit the clock but retain API text and the Wi-Fi indicator.
- API text defaults to 64 px, configurable per request with `text_size` from 32–96 px. Short lines stay centered; overflow scrolls right to left at full size instead of becoming tiny.
- The default 11-entry idle group includes standing, pool float, skateboard, headphones, sleeping, reading, coffee, kite, swaying, `windows_bsod` and `windows_shutdown`, with 30 seconds per selection. Automatic rotation gives each eligible normal entry 10 appearances per cycle and each retro entry one; group membership controls eligibility, and retro-only groups alternate equally. Physical buttons step through the configured order without weights; explicit API actions are immediate and bypass rarity. Configure `actions` and `interval` through `GET`/`POST /api/idle`; persisted groups are not silently migrated.
- `windows_bsod` and `windows_shutdown` are visual effects only: they never crash, restart or shut down the computer. Each defaults to 20 seconds and peeks once after 3 seconds, finishing by 8 seconds; see the [duration-capable API examples](docs/api.md#retro-windows-scenes).
- A small top-right Wi-Fi icon distinguishes connected, disconnected and unavailable radios. Linux link state refreshes every two seconds without Internet probes; this indicates Wi-Fi association, not Internet availability. Desktop previews without Linux sysfs show the unavailable icon.
- The optional browser mirror shows the same native frames. The magnifying-glass animation uses no camera or microphone.

Clawd and website artwork © Anthropic. Unofficial project; brand marks belong to their owners. See [artwork and redistribution notes](docs/artwork.md#source-attribution-and-redistribution).

**Native display output has been exercised on a Pi Zero W running Raspberry Pi OS Trixie with the Waveshare 2.8-inch DPI panel.** The [systemd unit](deploy/pipclock.service) renders directly through KMSDRM, without a desktop or browser, and starts at boot.

The installed Pi exposes its bearer-authenticated API directly on the trusted LAN. Use the [API cookbook](docs/api.md#client-setup-on-this-mac) for requests without SSH, and the [Pi runbook](docs/raspberry-pi.md) for the complete host configuration, change history and administrative commands.
