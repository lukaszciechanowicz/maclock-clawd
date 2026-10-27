# Maclock Clawd: a desk companion

A tiny animated Clawd, clock and notification display for a **640 × 480 landscape screen**. Built for a Raspberry Pi Zero W inside a Maclock enclosure, with a Mac preview for trying all 62 reactions before touching the hardware.

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
| [API reference](docs/api.md) | Endpoints, mood + text captions, timed notes, authentication and the full reaction table. |
| [Claude Code integration](docs/claude-code.md) | Opt-in lifecycle hooks, event mappings and secure connections. |
| [Artwork and attribution](docs/artwork.md) | Source credits, rights notices and rebuilding the animations/gallery. |

## How it works

- Python and pygame render natively; the Pi needs no browser, LLM or runtime animation downloads.
- Custom block-shaped poses sit alongside bundled frames from claude.dev. The side rectangles are Clawd's arms.
- HTTP events select reactions; captions and bottom notes expire on timers while the clock/date stay visible.
- The optional browser mirror shows the same native frames. The magnifying-glass animation uses no camera or microphone.

Clawd and website artwork © Anthropic. Unofficial project; brand marks belong to their owners. See [artwork and redistribution notes](docs/artwork.md#source-attribution-and-redistribution).

**Native display output has been exercised on a Pi Zero W running Raspberry Pi OS Trixie with the Waveshare 2.8-inch DPI panel.** The [systemd unit](deploy/pipclock.service) renders directly through KMSDRM, without a desktop or browser, and starts at boot.

The unit expects the source in `/opt/maclock-clawd`, distro `python3-pygame` 2.6.1, `libgbm1`, `libegl1`, `libgles2`, `libgl1-mesa-dri`, `fontconfig` and `fonts-dejavu-core`. Its `pipclock` system account needs the `video`, `render` and `input` groups; the service takes over `tty1` from getty.

`--rotation 90` maps the logical 640 × 480 scene onto the panel's native 480 × 640 pixels. Angles are counterclockwise; use `270` for the opposite mounting, `180` for an upside-down landscape panel, or the default `0` for a normal landscape display. Browser previews stay landscape. The original Pi Zero W smoke run, including two native frame captures, averaged about 5 fps; the `--fps` setting is a ceiling, not a guaranteed rate.
