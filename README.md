# Maclock: a Clawd desk companion

A tiny animated Clawd, clock and notification display for a **640 × 480 landscape screen**. The terracotta block character follows the supplied Clawd reference: stepped sides, two square black eyes and four short feet. A warm retro Macintosh palette frames expressive movements and an always-visible clock/date. A Mac preview lets you approve the character before committing to hardware. The intended appliance is a first-generation Raspberry Pi Zero W with a horizontally mounted Waveshare 2.8-inch DPI LCD.

**Some of the animations are my own custom creations, made specifically for this project. Other animations use the animation library from [claude.dev](https://claude.dev/). That library was the inspiration for this project's animation style and Clawd's movement.**

**Hardware support is a proposal, not a certified appliance image.** No actual Pi performance, temperature, power, memory or frame-rate measurements are available. Display-driver compatibility and physical fit remain unverified, especially on the original ARMv6 Zero W. Nothing here installs an overlay or solves the display driver for you.

## Architecture

- Python 3.11+ and pygame 2.6.1 draw a logical 640 × 480 landscape surface, targeting 24 frames per second by default. The Pi uses native SDL rendering, not a browser or an LLM.
- The 57 actions combine 14 custom native animations with 43 website animations: frames baked offline from 35 selected claude.dev Lottie sources and eight embedded pixel animations. Website actions use the actual source poses, not procedural approximations.
- A standard-library HTTP server receives small state/message commands. Rendering and HTTP share a latest-event-wins state model with monotonic expiry timers.
- Events animate the character; a separate timed text message replaces only the bottom status area. The clock/date stay visible. New messages replace old messages; their timer is independent of the current animation. Clawd deliberately leaves the screen briefly during `scared`.
- The optional desktop browser mirror refreshes at 12 fps. JPEG frames are generated only with `--preview`; normal Pi operation does not pay the encoding cost. The browser displays the same native frames rather than running a separate animation engine.
- Character poses run at 12 fps, independently of the configurable display-loop rate. Website frames are bundled raster atlases: startup reads their metadata, and the renderer lazily decodes and caches **one current atlas**, replacing it when the action changes. All animation works offline, with no runtime browser, Lottie engine or network requests.
- The one-atlas cache bounds decoded animation memory instead of retaining every action. Bundled frames increase package/storage size, and switching actions can incur an atlas decode; these are resource tradeoffs, not a measured Pi Zero performance guarantee.
- Claude Code sends lifecycle events to the same local API. Clawd is an observational companion, never an approval or permission gate.
- Custom poses preserve stepped body blocks, two eyes and short feet. The two side rectangles **are** the arms; there are no attached stick limbs, palms or fingers. Coffee is held at the side without drinking; the book's cover faces the viewer while its pages face Clawd.

### Source attribution and redistribution

Clawd and the website source artwork remain **copyright Anthropic**. This is an unofficial project, not affiliated with or endorsed by Anthropic. The custom artwork follows user-supplied Clawd references; it is not a claim of original character ownership.

The website sources are published on [claude.dev](https://claude.dev/). Its [interaction script](https://claude.dev/_next/static/chunks/3vrq03-z-93vf.js) supplies the act inventory and header-wave playback behavior; the [sprite data module](https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js) contains kite, walking, skateboard, car, scooter, bike, astronaut and pool frames. The complete selected source-file inventory is linked in the action catalog below and recorded in [`pipclock/catalog.py`](pipclock/catalog.py). Header `wave` follows the source's forward-then-backward playback; `walking` uses source frames 8–23 for its gait. Coffee and sunglasses deliberately use the requested custom variants instead of the site's corresponding acts.

Publicly reachable asset URLs **do not establish an open-source or open-content license**. No project license has been selected. Source copyright remains Anthropic's, and character/trademark and asset permissions need review **before public redistribution**, including redistribution of baked or modified frames. Bundling frames does not remove the source rights restrictions.

The existing package, CLI and environment-variable names remain `pipclock` and `PIPCLOCK_TOKEN`; the on-screen character is Clawd.

### Rebuilding the bundled artwork

The runtime needs only pygame and the included PNG files. Baking is a separate desktop-only developer task:

```sh
.venv/bin/pip install -e '.[artwork]'
.venv/bin/playwright install chromium
.venv/bin/python tools/bake_clawd.py
```

To use an existing Chrome installation instead of downloading Chromium:

```sh
.venv/bin/python tools/bake_clawd.py \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The baker fetches the catalog in a browser, evaluates Lottie only in that browser, and converts it into native-size atlases. Pixel sprite data is parsed as JSON-compatible literals, not executed. The manifest records source URLs, SHA-256 hashes, timing, atlas dimensions and decoded-memory sizes. Bake before packaging; do not install Playwright or run the baker on the Pi.

### Generated artwork footprint

| Measurement | Generated value |
| --- | --- |
| Bundled atlases and manifest on disk | 4,282,305 bytes (about 4.08 MiB) |
| Largest single decoded atlas | 26,107,776 bytes (about 24.9 MiB) |
| Native baked frames | 2,732 across 43 atlases |

These are generated asset sizes, not Pi process-memory or performance measurements. Only one decoded atlas is retained; loading/conversion can temporarily hold both a source surface and its display-formatted copy. Python, SDL, fonts, display surfaces and the OS require additional RAM.

## Local Mac preview

From the repository root, with Python 3.12 installed:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m pipclock --headless --preview
```

For the recommended browser-only desktop preview, keep that process running and open <http://127.0.0.1:8765/> for the live native-rendered mirror and controls. Startup plays an eight-second header wave, then settles into idle. Stop the process with Ctrl-C.

The categorized controls expose all 57 actions. **Play all actions** makes one pass through the catalog; its button count and estimated animation time are calculated from the controls. Thinking, waiting and sleeping are shortened for this tour. **Stop demo**, any manual action, sending a note, editing a control, hiding the tab, or leaving the page cancels the tour. Stopping prevents subsequent actions; it does not undo an action already received by the device. No demo runs automatically on the Pi.

For a native pygame window with the optional browser mirror:

```sh
.venv/bin/python -m pipclock --preview
```

Closing the native pygame window stops the HTTP server too. Use the recommended `--headless --preview` command when the browser should not depend on an open native window. If the browser reports `ERR_CONNECTION_REFUSED`, start that process before reloading the page.

`--headless` requires `--preview` and uses SDL's dummy video driver. It is not the recommended Pi display mode. `--fullscreen` requests native fullscreen. `--fps` accepts 1–60 (default 24); `--host` and `--port` default to `127.0.0.1` and `8765`. Preview is available only with loopback binding.

## API

These examples use the default token-free loopback development server:

```sh
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/state

curl -X POST http://127.0.0.1:8765/api/event \
  -H 'Content-Type: application/json' \
  -d '{"event":"dance","duration":12}'

curl -X POST http://127.0.0.1:8765/api/message \
  -H 'Content-Type: application/json' \
  -d '{"text":"Build finished. Time for a stretch!","duration":20}'

curl -X POST http://127.0.0.1:8765/api/event \
  -H 'Content-Type: application/json' \
  -d '{"event":"idle"}'
```

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Public JSON liveness response. |
| `GET /api/state` | Current snapshot: `state`, `elapsed`, `message`, `message_remaining`. |
| `POST /api/event` | Any action listed below; optional `duration` in seconds, positive and at most 3600. Omit duration for the action default. |
| `POST /api/message` | `text`: 1–280 Unicode characters; required `duration`: positive seconds, at most 3600. |
| `POST /hooks/claude` | Claude Code JSON lifecycle payload; recognized events receive HTTP 204 with no decision output. |
| `GET /`, `GET /frame.jpg` | Desktop HTML/JPEG mirror, only when `--preview` is enabled. |

A new event immediately replaces the previous event; expiry returns to idle. An event does not clear an active message. Message expiry reveals the then-current live status, not a saved historical status. This is a single display, with no queue, durable history, multi-session aggregation or guaranteed delivery.

### Actions

The API accepts the following **57 event names**. Default durations apply when `duration` is omitted; the browser tour uses shorter samples for long-lived statuses.

#### Custom native actions

| API event | Default duration | Animation |
| --- | --- | --- |
| `idle` | Until replaced | Quiet breathing and blinking. |
| `smile` | 8 s | Stepped happy eyes and a gentle bob, without adding a mouth. |
| `knock` | 8 s | A foreshortened side block taps toward the viewer with screen/glass impact marks; no door. |
| `waiting` | 60 s | Patient glances. |
| `coffee` | 12 s | Hold a large steaming mug at the side, stay still and blink; no lifting, drinking or mouth. |
| `reading` | 20 s | Look down into an open book with pages facing Clawd and the back/cover facing the viewer; a top-edge page turn. |
| `lens` | 12 s | Inspect through a large magnifying glass with a magnified eye, held by a side block. |
| `ok` | 8 s | Raise a side block, nod, and show an OK! bubble/check mark; no drawn hand. |
| `scared` | 8 s | Startle with eyes only, flee behind the right edge, disappear, re-enter from the left and return home; no mouth. |
| `phone_ringing` | 10 s | Rapid alternating jitter and vibration marks in intermittent bursts; no audio or real phone integration. |
| `sunglasses` | 12 s | Wear black stepped pixel glasses with white checker highlights and a subtle bob; no mouth. |
| `deal_with_it` | 10 s | The same glasses fall from above, settle with a small bounce, then “Deal with it.” appears; hold the final pose. |
| `closeup` | 12 s | Approach the screen until only the eyes are visible, glance around, smile with the eyes, then return. |
| `heart_eyes` | 10 s | Eyes become pulsing hearts. |

#### Website-frame actions

These 43 actions render bundled frames from the linked Anthropic website sources. Durations below are API defaults, not necessarily the source animation's cycle length.

| API event | Default duration | Website animation / source |
| --- | --- | --- |
| `wave` | 8 s | [Header wave](https://claude.dev/shared/video/clawd-waving.json), played forward then backward. |
| `looking` | 12 s | [Look around](https://claude.dev/shared/video/clawd-looking.json). |
| `walking` | 12 s | [Go for a walk](https://claude.dev/shared/video/clawd-walking.json), gait frames 8–23. |
| `bounce` | 8 s | [Jump](https://claude.dev/shared/video/acts/Clawd-Jumping.json). |
| `thinking` | 300 s | [Think](https://claude.dev/shared/video/acts/Clawd-Thinking.json). |
| `laptop` | 12 s | [Laptop time](https://claude.dev/shared/video/acts/Clawd-Laptop.json). |
| `phone` | 12 s | [Check the phone](https://claude.dev/shared/video/acts/Clawd-Phone.json). |
| `desktop` | 12 s | [Desktop time](https://claude.dev/shared/video/acts/Clawd-Desktop.json). |
| `notebook` | 12 s | [Take notes](https://claude.dev/shared/video/acts/Clawd-Notebook.json). |
| `headphones` | 12 s | [Headphones on](https://claude.dev/shared/video/acts/Clawd-Headphones.json). |
| `watch` | 10 s | [Check the watch](https://claude.dev/shared/video/acts/Clawd-Watch.json). |
| `turning` | 8 s | [Turn around](https://claude.dev/shared/video/acts/Clawd-Turning.json). |
| `sleeping` | 30 s | [Take a nap](https://claude.dev/shared/video/acts/Clawd-Snooze.json). |
| `lightbulb` | 10 s | [A bright idea](https://claude.dev/shared/video/acts/Clawd-Lightbulb.json). |
| `spark` | 10 s | [Make a spark](https://claude.dev/shared/video/acts/Clawd-Spark.json). |
| `swaying` | 12 s | [Sway along](https://claude.dev/shared/video/acts/Clawd-Swaying.json). |
| `juggling` | 12 s | [Juggle](https://claude.dev/shared/video/acts/Clawd-Juggling.json). |
| `hula_hoop` | 12 s | [Hula hoop](https://claude.dev/shared/video/acts/Clawd-HulaHoop.json). |
| `bubble` | 12 s | [Blow a bubble](https://claude.dev/shared/video/acts/Clawd-Bubble.json). |
| `fishing` | 12 s | [Go fishing](https://claude.dev/shared/video/acts/Clawd-Fishing.json). |
| `watering` | 12 s | [Water a plant](https://claude.dev/shared/video/acts/Clawd-Watering.json). |
| `berry_picking` | 12 s | [Pick berries](https://claude.dev/shared/video/acts/Clawd-BerryPicking.json). |
| `blooming` | 12 s | [Bloom](https://claude.dev/shared/video/acts/Clawd-Blooming.json). |
| `rainbow` | 12 s | [Make a rainbow](https://claude.dev/shared/video/acts/Clawd-Rainbow.json). |
| `rose` | 12 s | [A rose for you](https://claude.dev/shared/video/acts/Clawd-Rose.json). |
| `heart` | 12 s | [Send a heart](https://claude.dev/shared/video/acts/Clawd-Heart.json). |
| `arcade` | 12 s | [Arcade break](https://claude.dev/shared/video/acts/Clawd-Arcade.json). |
| `meditating` | 12 s | [Meditate](https://claude.dev/shared/video/acts/Clawd-Meditating.json). |
| `excited` | 10 s | [Get excited](https://claude.dev/shared/video/acts/Clawd-Excited.json). |
| `jumping_happy` | 10 s | [Happy jumps](https://claude.dev/shared/video/acts/Clawd-JumpingHappy.json). |
| `dance` | 12 s | [Dance](https://claude.dev/shared/video/acts/Clawd-Dancing.json). |
| `confetti` | 12 s | [Confetti](https://claude.dev/shared/video/acts/Clawd-Confetti.json). |
| `dancing_happy` | 12 s | [Happy dance](https://claude.dev/shared/video/acts/Clawd-DancingHappy.json). |
| `breakdancing` | 12 s | [Breakdance](https://claude.dev/shared/video/acts/Clawd-BreakDancing.json). |
| `confetti_happy` | 12 s | [Happy confetti](https://claude.dev/shared/video/acts/Clawd-ConfettiHappy.json). |
| `kite` | 20 s | Fly a kite, from the [embedded pixel sprite data](https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js). |
| `pixel_walk` | 12 s | Pixel stroll, from the embedded sprite data. |
| `skate` | 12 s | Skateboard, from the embedded sprite data. |
| `car` | 12 s | Take a drive, from the embedded sprite data. |
| `scooter` | 12 s | Ride a scooter, from the embedded sprite data. |
| `bike` | 12 s | Ride a bike, from the embedded sprite data. |
| `astronaut` | 12 s | Float in space, from the embedded sprite data. |
| `pool` | 12 s | Float in the pool, from the embedded sprite data. |

The lens is theatrical animation only: **no camera, microphone or room sensing**. Explicit actions replay when sent again; repeated `thinking` events instead extend the watchdog without resetting its motion. The scared sequence repeats within its active duration; its default duration includes a complete exit and return. `deal_with_it` drops its glasses once per event and holds the result rather than repeatedly dropping them. Unknown event names receive HTTP 400; there are no compatibility aliases for removed actions.

```sh
curl http://127.0.0.1:8765/api/event \
  -H 'Content-Type: application/json' \
  -d '{"event":"coffee","duration":12}'
```

Messages wrap at word boundaries and split long words; dense notes shrink to fit the panel without covering the clock or action scene. Blank notes and control characters other than newlines are rejected. Unicode glyph coverage depends on locally installed fonts; missing scripts or emoji may display replacement boxes.

All POSTs require `Content-Type: application/json`; bodies are limited to 16 KiB and malformed input is rejected. There is no CORS support. For authentication, set `PIPCLOCK_TOKEN` in the server environment and add `Authorization: Bearer ...` to API/hook requests:

```sh
export PIPCLOCK_TOKEN="$(openssl rand -hex 32)"
.venv/bin/python -m pipclock --headless --preview
# In another terminal, set the same token before making requests:
curl http://127.0.0.1:8765/api/state \
  -H "Authorization: Bearer ${PIPCLOCK_TOKEN}"
```

The token protects `/api/*` and `/hooks/*`, not `/health` or the loopback-only preview. Enter the token into the browser mirror's password field when needed; it is not embedded in HTML. Loopback is not authentication against other processes/users on the same machine.

## Claude Code integration (opt-in)

[`examples/claude-hooks.json`](examples/claude-hooks.json) follows the current official [Claude Code hooks reference](https://code.claude.com/docs/en/hooks): HTTP handlers with `timeout: 2`, an Authorization header interpolated from `${PIPCLOCK_TOKEN}`, and `allowedEnvVars: ["PIPCLOCK_TOKEN"]`. It includes every mapped event:

| Claude event | Clawd reaction |
| --- | --- |
| `SessionStart` | `wave`, 8 seconds |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `thinking`, 300 seconds |
| `Stop` | `bounce`, 8 seconds |
| `Notification`, `PermissionRequest` | `waiting`, 60 seconds |
| `PostToolUseFailure`, `StopFailure` | `knock`, 8 seconds |
| `SessionEnd` | `idle` |

No active hooks are installed by this repository. To opt in, review the example and merge its `hooks` entries into your chosen Claude settings file (for example `.claude/settings.local.json`), preserving existing settings and hooks. Export the same `PIPCLOCK_TOKEN` before starting Claude Code and the companion server. Restart/review Claude's hook configuration as directed by its documentation. Organization HTTP URL/environment allowlists may also need to permit this endpoint and variable. Remove only these entries to opt out.

The example posts real Claude payloads. The app ignores prompt text, tool arguments, transcripts and paths and uses only the event name; nevertheless Claude sends the complete payload over the connection. Do not send it to an untrusted endpoint. The 16 KiB limit can reject large real tool payloads: such notifications will not update the display. Hooks return no permission decisions; a waiting animation does not approve anything. Hook failures are observational, not a security control.

`thinking` is a 300-second watchdog refreshed by lifecycle/tool activity, **not** token-level inference or proof that Claude is still working. Events from multiple sessions/subagents compete: the most recent accepted event wins, and a session ending can clear another session's status. No attempt is made to reconstruct task ownership.

### Recommended Mac-to-Pi connection: SSH tunnel

Keep the Pi server bound to loopback. On the Mac running Claude, open this tunnel (replace `pipclock@raspberrypi.local` with your provisioned SSH login/host):

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 pipclock@raspberrypi.local
```

The example hook URL remains `http://127.0.0.1:8765/hooks/claude`. Do not also run the Mac preview on that port. The tunnel encrypts traffic; use the same bearer token at both ends. The service account need not allow SSH: a separate provisioned SSH account can forward to Pi loopback.

LAN binding is optional and requires a token:

```sh
export PIPCLOCK_TOKEN="$(openssl rand -hex 32)"
python3 -m pipclock --fullscreen --host 0.0.0.0
```

Change the hook URL to the Pi's address only if you deliberately choose LAN access. Plain HTTP does not encrypt the token or Claude payloads: prefer SSH, restrict firewall access and never expose this port to the Internet. Preview cannot be enabled with this non-loopback binding.

## Raspberry Pi deployment

### Hardware prerequisites and limits

Read the manufacturer material first:

- [Waveshare 2.8inch DPI LCD wiki](https://www.waveshare.com/wiki/2.8inch_DPI_LCD): display wiring, timings, OS/driver instructions and hardware variants.
- [Maclock manufacturer/shop](https://www.maclock.shop/en): enclosure/product details. This project does not establish that this particular panel, Pi board, GPIO stack, connectors and cable clearances fit that enclosure.

The **original Pi Zero W is ARMv6**. Use a 32-bit OS image explicitly supporting ARMv6; a 64-bit image or software built only for ARMv7/ARMv8 is not suitable. Confirm that the image also supplies Python 3.11+ and a working distro pygame/SDL stack. The declared pygame development version is 2.6.1; distro package versions may differ and require hardware validation. Installing `python3-pygame` with apt avoids relying on unavailable ARMv6 wheels or a long local source build. A 32 GB card is a reasonable capacity for the proposed OS/application, not a measured storage requirement.

Before enabling a service, separately establish a working **640 × 480 landscape output** using the vendor's instructions for your exact board and OS. The panel's native timing is 480 × 640, so configure a 90° or 270° display rotation to match its mounting; rotate/calibrate touch coordinates as well. Confirm native SDL KMSDRM (or your working local graphical session) can open that landscape output. Overlay availability, DPI pin use, rotation, original-Zero compatibility and seat/console access are unresolved until tested on the actual hardware. Do not copy an arbitrary overlay recipe from a newer Pi and assume it applies.

The application and preview use a true landscape layout, not a stretched portrait image. Check the active area, PCB, mounting points, GPIO header height and USB power clearance before removing the original electronics. Waveshare lists panel consumption as 5 V / 160 mA; that excludes the Pi and is not a whole-device power measurement. Start with a suitable regulated 5 V supply. Do not assume the original clock battery/charging board can safely power the replacement electronics.

### Run natively first

Copy this repository to the Pi and run from its root after configuring the display:

```sh
sudo apt update
sudo apt install python3 python3-pygame
python3 --version
python3 -m pipclock --fullscreen
```

Use Python 3.11 or newer. Running directly from the repository uses the apt-provided pygame without a pip wheel build. If the OS repositories cannot supply the required Python/SDL stack for ARMv6, that is an OS compatibility prerequisite to resolve, not something this application installs automatically. Do not enable `--preview` on the Pi: native fullscreen does not encode JPEG frames. A 24 fps target is configurable, not a measured first-generation Zero result.

### Optional systemd service

[`deploy/pipclock.service`](deploy/pipclock.service) is an **opt-in Linux system service running as the unprivileged user `pipclock`**, with repository files in `/opt/maclock`. It binds loopback and starts native fullscreen without preview. It is not a portable display-driver installer.

On a system with `useradd`, provision the account and copy your checkout into `/opt/maclock` (the directory must contain the `pipclock` package):

```sh
sudo useradd --system --user-group --home-dir /opt/maclock --shell /usr/sbin/nologin pipclock
sudo install -d -o pipclock -g pipclock /opt/maclock
sudo cp -R . /opt/maclock/
sudo chown -R pipclock:pipclock /opt/maclock
```

Run the copy commands from the source checkout, not from `/opt/maclock` itself. If the account/directory already exists, reuse it instead of recreating it. Provision local tty/seat, DRM/render and input permissions for this account using your OS's actual device ownership and access model. A system service does not automatically inherit an interactive graphical login or its permissions. The correct SDL backend, console ownership, device groups and any systemd drop-ins depend on that setup; this unit intentionally does not guess them, grant root, or claim that enabling it alone produces a display.

Optionally create `/etc/pipclock.env` with a shared secret for hooks/API clients:

```sh
sudo sh -c 'umask 077; printf "PIPCLOCK_TOKEN=%s\n" "$(openssl rand -hex 32)" > /etc/pipclock.env'
```

Transfer the token securely to the Claude environment; do not commit it. The root-owned environment file is read by systemd. Keep the unit's loopback binding for the SSH tunnel. Once native rendering and permissions work for the service account, install and explicitly enable the unit:

```sh
sudo install -m 0644 deploy/pipclock.service /etc/systemd/system/pipclock.service
sudo systemctl daemon-reload
sudo systemctl enable --now pipclock.service
sudo journalctl -u pipclock.service -f
```

To stop and opt out: `sudo systemctl disable --now pipclock.service`. A restart loop or black screen needs investigation of display/seat/SDL permissions and the driver, not a switch to a root service. Browser-preview success on a Mac does not validate Pi hardware support.

## Verification

Run the behavioral regression suite from the repository root:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The current macOS checks passed **11 behavioral tests**, including header-wave reversal, the walking loop boundary, timers, replay, rejected removed events, authentication and non-decision hooks. A live smoke run sent every one of the 57 actions through HTTP and received native JPEG frames, checked UI/API action parity, rejected the removed yawning actions, verified a 280-character note expired without interrupting `closeup`, replayed the glasses drop, and exercised Claude hook transitions. Visual keyframes covered every action, the full closeup/return and falling-glasses sequences. Separate transition checks confirmed the glasses hold their final pose, closeup returns home, and square eyes become hearts. The built wheel included all 43 atlases and rendered all 57 actions from its extracted installed package. Browser checks exercised the dynamic 57-action controls and manual demo cancellation; the full ten-minute catalog tour was not run end-to-end. Browser-preview success on a Mac does not establish performance, rotation or touchscreen behavior on Raspberry Pi hardware.
