# Maclock Clawd: a desk companion

An animated Clawd and calculator-style clock for a **640 × 480 landscape screen**. Built for a Raspberry Pi Zero W inside a Maclock enclosure, with a Mac preview for trying all 62 reactions before touching the hardware.

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

## Documentation

| Guide | Contents |
| --- | --- |
| [Animation gallery](docs/gallery.md) | All 62 animated GIFs, grouped like the preview and arranged three per row. |
| [API cookbook and reference](docs/api.md) | Copy/paste LAN curl and Python examples, text sizes/scrolling, idle configuration, authentication and all 62 reactions. |
| [Raspberry Pi configuration and operations](docs/raspberry-pi.md) | Recorded SD/boot, display, USB/SSH, locale and package changes; native service, secrets, deployment, backups and troubleshooting. |
| [Claude Code integration](docs/claude-code.md) | Opt-in lifecycle hooks, event mappings and secure connections. |
| [Artwork and attribution](docs/artwork.md) | Source credits, rights notices and rebuilding the animations/gallery. |

## How it works

- Python and pygame render natively; the Pi needs no browser, LLM or runtime animation downloads.
- Custom block-shaped poses sit alongside bundled frames from claude.dev. The side rectangles are Clawd's arms.
- A larger, consistently terracotta Clawd sits near the bottom of a flat sand background; no frame, date, slogans or lower status panel.
- The raised calculator-style clock uses bundled DSEG7 Classic digits and shows only hours and minutes. API captions and timed messages replace it above Clawd without shrinking the artwork; reaction captions take priority over timed messages.
- API text defaults to 64 px, configurable per request with `text_size` from 32–96 px. Short lines stay centered; overflow scrolls right to left at full size instead of becoming tiny.
- Idle rotates through standing, pool float, skateboard, headphones, sleeping, reading, coffee, kite and swaying every 30 seconds. Configure the ordered group and interval through `GET`/`POST /api/idle`; explicit actions interrupt it and idle resumes on expiry.
- A small top-right Wi-Fi icon distinguishes connected, disconnected and unavailable radios. Linux link state refreshes every two seconds without Internet probes; this indicates Wi-Fi association, not Internet availability. Desktop previews without Linux sysfs show the unavailable icon.
- The optional browser mirror shows the same native frames. The magnifying-glass animation uses no camera or microphone.

Clawd and website artwork © Anthropic. Unofficial project; brand marks belong to their owners. See [artwork and redistribution notes](docs/artwork.md#source-attribution-and-redistribution).

**Native display output has been exercised on a Pi Zero W running Raspberry Pi OS Trixie with the Waveshare 2.8-inch DPI panel.** The [systemd unit](deploy/pipclock.service) renders directly through KMSDRM, without a desktop or browser, and starts at boot.

The installed Pi exposes its bearer-authenticated API directly on the trusted LAN. Use the [API cookbook](docs/api.md#client-setup-on-this-mac) for requests without SSH, and the [Pi runbook](docs/raspberry-pi.md) for the complete host configuration, change history and administrative commands.
