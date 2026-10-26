# Maclock Clawd: a desk companion

A tiny animated Clawd, clock and notification display for a **640 × 480 landscape screen**. The terracotta block character follows the supplied Clawd reference: stepped sides, two square black eyes and four short feet. A warm retro Macintosh palette frames expressive movements and an always-visible clock/date. A Mac preview lets you approve the character before committing to hardware. The intended appliance is a first-generation Raspberry Pi Zero W with a horizontally mounted Waveshare 2.8-inch DPI LCD.

Repository: [lukaszciechanowicz/maclock-clawd](https://github.com/lukaszciechanowicz/maclock-clawd).

**Some of the animations are my own custom creations, made specifically for this project. Other animations use the animation library from [claude.dev](https://claude.dev/). That library was the inspiration for this project's animation style and Clawd's movement.**

**Hardware support is a proposal, not a certified appliance image.** No actual Pi performance, temperature, power, memory or frame-rate measurements are available. Display-driver compatibility and physical fit remain unverified, especially on the original ARMv6 Zero W. Nothing here installs an overlay or solves the display driver for you.

## Architecture

- Python 3.11+ and pygame 2.6.1 draw a logical 640 × 480 landscape surface, targeting 24 frames per second by default. The Pi uses native SDL rendering, not a browser or an LLM.
- The 62 actions combine 19 custom native animations with 43 website animations: frames baked offline from 35 selected claude.dev Lottie sources and eight embedded pixel animations. Website actions use the actual source poses, not procedural approximations.
- A standard-library HTTP server receives small state/message commands. Rendering and HTTP share a latest-event-wins state model with monotonic expiry timers.
- Events animate the character; a separate timed text message replaces only the bottom status area. The query API can pair an animation with a timed caption above Clawd. Both leave the clock/date visible; bottom notes have an independent timer. Clawd deliberately leaves the screen briefly during `scared`.
- The optional desktop browser mirror refreshes at 12 fps. JPEG frames are generated only with `--preview`; normal Pi operation does not pay the encoding cost. The browser displays the same native frames rather than running a separate animation engine.
- Character poses run at 12 fps, independently of the configurable display-loop rate. Website frames are bundled raster atlases: startup reads their metadata, and the renderer lazily decodes and caches **one current atlas**, replacing it when the action changes. All animation works offline, with no runtime browser, Lottie engine or network requests.
- The one-atlas cache bounds decoded animation memory instead of retaining every action. Bundled frames increase package/storage size, and switching actions can incur an atlas decode; these are resource tradeoffs, not a measured Pi Zero performance guarantee.
- Claude Code sends lifecycle events to the same local API. Clawd is an observational companion, never an approval or permission gate.
- Custom poses preserve stepped body blocks, two eyes and short feet. The two side rectangles **are** the arms; there are no attached stick limbs, palms or fingers. Coffee is held at the side without drinking; the book's cover faces the viewer while its pages face Clawd.

### Source attribution and redistribution

Clawd and the website source artwork remain **copyright Anthropic**. This is an unofficial project, not affiliated with or endorsed by Anthropic. The custom artwork follows user-supplied Clawd references; it is not a claim of original character ownership.

The website sources are published on [claude.dev](https://claude.dev/). Its [interaction script](https://claude.dev/_next/static/chunks/3vrq03-z-93vf.js) supplies the act inventory and header-wave playback behavior; the [sprite data module](https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js) contains kite, walking, skateboard, car, scooter, bike, astronaut and pool frames. The complete selected source-file inventory is linked in the action catalog below and recorded in [`pipclock/catalog.py`](pipclock/catalog.py). Header `wave` follows the source's forward-then-backward playback; `walking` uses source frames 8–23 for its gait. Coffee and sunglasses deliberately use the requested custom variants instead of the site's corresponding acts.

Publicly reachable asset URLs **do not establish an open-source or open-content license**. No project license has been selected. Source copyright remains Anthropic's, and character/trademark and asset permissions need review **before public redistribution**, including redistribution of baked or modified frames. Bundling frames does not remove the source rights restrictions.

Flag artwork uses official marks from [AWS](https://aws.amazon.com/), [ShipStation](https://www.shipstation.com/wp-content/uploads/2026/02/logo-ss-primary-rgb-1-1.svg) and [Stamps.com](https://www.stamps.com/wp-content/uploads/2026/02/logo-stamps-primary-rgb-1-1.svg). These marks belong to their respective owners and do not imply sponsorship or endorsement. The native flag animations are custom; the logos are not original project artwork. Source URLs and SHA-256 hashes are recorded in [`pipclock/assets/brands/sources.json`](pipclock/assets/brands/sources.json). See also the [AWS trademark guidelines](https://aws.amazon.com/trademark-guidelines/).

The existing package, CLI and environment-variable names remain `pipclock` and `PIPCLOCK_TOKEN`; the on-screen character is Clawd.

### Rebuilding the bundled artwork

The runtime needs only pygame and the included PNG files. Baking is a separate desktop-only developer task:

```sh
.venv/bin/pip install -e '.[artwork]'
.venv/bin/playwright install chromium
.venv/bin/python tools/bake_clawd.py
.venv/bin/python tools/bake_brand_marks.py
```

To use an existing Chrome installation instead of downloading Chromium:

```sh
.venv/bin/python tools/bake_clawd.py \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The baker fetches the catalog in a browser, evaluates Lottie only in that browser, and converts it into native-size atlases. Pixel sprite data is parsed as JSON-compatible literals, not executed. The manifest records source URLs, SHA-256 hashes, timing, atlas dimensions and decoded-memory sizes. Bake before packaging; do not install Playwright or run the baker on the Pi.

The brand-mark baker rasterizes official SVG artwork into small transparent PNGs. It accepts the same `--browser-executable` option. Brand flags and their flutter frames are prepared once at renderer startup; there are no runtime logo downloads.

### Generated artwork footprint

| Measurement | Generated value |
| --- | --- |
| Bundled atlases and manifest on disk | 4,282,305 bytes (about 4.08 MiB) |
| Largest single decoded atlas | 26,107,776 bytes (about 24.9 MiB) |
| Native baked frames | 2,732 across 43 atlases |
| Official brand PNGs and source metadata on disk | 9,221 bytes |
| Cached native flutter frames | 10,360,320 bytes (about 9.88 MiB), across four flags |

These are generated asset sizes, not Pi process-memory or performance measurements. Only one decoded website atlas is retained; loading/conversion can temporarily hold both a source surface and its display-formatted copy. The custom flag cache and reusable caption canvases are additional fixed surfaces. Python, SDL, fonts, display surfaces and the OS require additional RAM.

## Local Mac preview

```sh
git clone https://github.com/lukaszciechanowicz/maclock-clawd.git
cd maclock-clawd
```

From the repository root, with Python 3.12 installed:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m pipclock --headless --preview
```

For the recommended browser-only desktop preview, keep that process running and open <http://127.0.0.1:8765/> for the live native-rendered mirror and controls. Startup plays an eight-second header wave, then settles into idle. Stop the process with Ctrl-C.

The categorized controls expose all 62 actions. **Play every action** makes one pass through the catalog; its button count and estimated animation time are calculated from the controls. Thinking, waiting and sleeping are shortened for this tour. **Stop demo**, any manual action, sending a note or overhead caption, editing a control, hiding the tab, or leaving the page cancels the tour. Stopping prevents subsequent actions; it does not undo an action already received by the device. No demo runs automatically on the Pi.

For a native pygame window with the optional browser mirror:

```sh
.venv/bin/python -m pipclock --preview
```

Closing the native pygame window stops the HTTP server too. Use the recommended `--headless --preview` command when the browser should not depend on an open native window. If the browser reports `ERR_CONNECTION_REFUSED`, start that process before reloading the page.

`--headless` requires `--preview` and uses SDL's dummy video driver. It is not the recommended Pi display mode. `--fullscreen` requests native fullscreen. `--fps` accepts 1–60 (default 24); `--host` and `--port` default to `127.0.0.1` and `8765`. Preview is available only with loopback binding.

## Animation gallery

All 62 actions, rendered by the same native renderer used on the device, **three per row**. Each preview loops; longer transitions include their approach, expression and return. The example clock/date is fixed so exports are reproducible. See [source attribution](#source-attribution-and-redistribution) for the distinction between custom animations and the claude.dev library.

<!-- BEGIN ANIMATION GALLERY -->
<table>
  <tr>
    <td align="center" width="33%"><strong>Idle</strong><br><code>idle</code><br><img src="docs/gallery/idle.gif" alt="Animated Clawd: Idle" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Smile</strong><br><code>smile</code><br><img src="docs/gallery/smile.gif" alt="Animated Clawd: Smile" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Knock</strong><br><code>knock</code><br><img src="docs/gallery/knock.gif" alt="Animated Clawd: Knock" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Waiting</strong><br><code>waiting</code><br><img src="docs/gallery/waiting.gif" alt="Animated Clawd: Waiting" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Coffee</strong><br><code>coffee</code><br><img src="docs/gallery/coffee.gif" alt="Animated Clawd: Coffee" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Reading</strong><br><code>reading</code><br><img src="docs/gallery/reading.gif" alt="Animated Clawd: Reading" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Lens</strong><br><code>lens</code><br><img src="docs/gallery/lens.gif" alt="Animated Clawd: Lens" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Ok</strong><br><code>ok</code><br><img src="docs/gallery/ok.gif" alt="Animated Clawd: Ok" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Scared</strong><br><code>scared</code><br><img src="docs/gallery/scared.gif" alt="Animated Clawd: Scared" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Phone ringing</strong><br><code>phone_ringing</code><br><img src="docs/gallery/phone_ringing.gif" alt="Animated Clawd: Phone ringing" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Sunglasses</strong><br><code>sunglasses</code><br><img src="docs/gallery/sunglasses.gif" alt="Animated Clawd: Sunglasses" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Deal with it</strong><br><code>deal_with_it</code><br><img src="docs/gallery/deal_with_it.gif" alt="Animated Clawd: Deal with it" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Closeup</strong><br><code>closeup</code><br><img src="docs/gallery/closeup.gif" alt="Animated Clawd: Closeup" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Heart eyes</strong><br><code>heart_eyes</code><br><img src="docs/gallery/heart_eyes.gif" alt="Animated Clawd: Heart eyes" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Polish flag</strong><br><code>flag_pl</code><br><img src="docs/gallery/flag_pl.gif" alt="Animated Clawd: Polish flag" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>AWS flag</strong><br><code>flag_aws</code><br><img src="docs/gallery/flag_aws.gif" alt="Animated Clawd: AWS flag" width="300" height="225"></td>
    <td align="center" width="33%"><strong>ShipStation flag</strong><br><code>flag_shipstation</code><br><img src="docs/gallery/flag_shipstation.gif" alt="Animated Clawd: ShipStation flag" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Stamps.com flag</strong><br><code>flag_stamps</code><br><img src="docs/gallery/flag_stamps.gif" alt="Animated Clawd: Stamps.com flag" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Cloud Engineering</strong><br><code>cloud_engineering</code><br><img src="docs/gallery/cloud_engineering.gif" alt="Animated Clawd: Cloud Engineering" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Header wave</strong><br><code>wave</code><br><img src="docs/gallery/wave.gif" alt="Animated Clawd: Header wave" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Look around</strong><br><code>looking</code><br><img src="docs/gallery/looking.gif" alt="Animated Clawd: Look around" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Go for a walk</strong><br><code>walking</code><br><img src="docs/gallery/walking.gif" alt="Animated Clawd: Go for a walk" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Jump</strong><br><code>bounce</code><br><img src="docs/gallery/bounce.gif" alt="Animated Clawd: Jump" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Think</strong><br><code>thinking</code><br><img src="docs/gallery/thinking.gif" alt="Animated Clawd: Think" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Laptop time</strong><br><code>laptop</code><br><img src="docs/gallery/laptop.gif" alt="Animated Clawd: Laptop time" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Check the phone</strong><br><code>phone</code><br><img src="docs/gallery/phone.gif" alt="Animated Clawd: Check the phone" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Desktop time</strong><br><code>desktop</code><br><img src="docs/gallery/desktop.gif" alt="Animated Clawd: Desktop time" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Take notes</strong><br><code>notebook</code><br><img src="docs/gallery/notebook.gif" alt="Animated Clawd: Take notes" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Headphones on</strong><br><code>headphones</code><br><img src="docs/gallery/headphones.gif" alt="Animated Clawd: Headphones on" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Check the watch</strong><br><code>watch</code><br><img src="docs/gallery/watch.gif" alt="Animated Clawd: Check the watch" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Turn around</strong><br><code>turning</code><br><img src="docs/gallery/turning.gif" alt="Animated Clawd: Turn around" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Take a nap</strong><br><code>sleeping</code><br><img src="docs/gallery/sleeping.gif" alt="Animated Clawd: Take a nap" width="300" height="225"></td>
    <td align="center" width="33%"><strong>A bright idea</strong><br><code>lightbulb</code><br><img src="docs/gallery/lightbulb.gif" alt="Animated Clawd: A bright idea" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Make a spark</strong><br><code>spark</code><br><img src="docs/gallery/spark.gif" alt="Animated Clawd: Make a spark" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Sway along</strong><br><code>swaying</code><br><img src="docs/gallery/swaying.gif" alt="Animated Clawd: Sway along" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Juggle</strong><br><code>juggling</code><br><img src="docs/gallery/juggling.gif" alt="Animated Clawd: Juggle" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Hula hoop</strong><br><code>hula_hoop</code><br><img src="docs/gallery/hula_hoop.gif" alt="Animated Clawd: Hula hoop" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Blow a bubble</strong><br><code>bubble</code><br><img src="docs/gallery/bubble.gif" alt="Animated Clawd: Blow a bubble" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Go fishing</strong><br><code>fishing</code><br><img src="docs/gallery/fishing.gif" alt="Animated Clawd: Go fishing" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Water a plant</strong><br><code>watering</code><br><img src="docs/gallery/watering.gif" alt="Animated Clawd: Water a plant" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Pick berries</strong><br><code>berry_picking</code><br><img src="docs/gallery/berry_picking.gif" alt="Animated Clawd: Pick berries" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Bloom</strong><br><code>blooming</code><br><img src="docs/gallery/blooming.gif" alt="Animated Clawd: Bloom" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Make a rainbow</strong><br><code>rainbow</code><br><img src="docs/gallery/rainbow.gif" alt="Animated Clawd: Make a rainbow" width="300" height="225"></td>
    <td align="center" width="33%"><strong>A rose for you</strong><br><code>rose</code><br><img src="docs/gallery/rose.gif" alt="Animated Clawd: A rose for you" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Send a heart</strong><br><code>heart</code><br><img src="docs/gallery/heart.gif" alt="Animated Clawd: Send a heart" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Arcade break</strong><br><code>arcade</code><br><img src="docs/gallery/arcade.gif" alt="Animated Clawd: Arcade break" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Meditate</strong><br><code>meditating</code><br><img src="docs/gallery/meditating.gif" alt="Animated Clawd: Meditate" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Get excited</strong><br><code>excited</code><br><img src="docs/gallery/excited.gif" alt="Animated Clawd: Get excited" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Happy jumps</strong><br><code>jumping_happy</code><br><img src="docs/gallery/jumping_happy.gif" alt="Animated Clawd: Happy jumps" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Dance</strong><br><code>dance</code><br><img src="docs/gallery/dance.gif" alt="Animated Clawd: Dance" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Confetti</strong><br><code>confetti</code><br><img src="docs/gallery/confetti.gif" alt="Animated Clawd: Confetti" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Happy dance</strong><br><code>dancing_happy</code><br><img src="docs/gallery/dancing_happy.gif" alt="Animated Clawd: Happy dance" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Breakdance</strong><br><code>breakdancing</code><br><img src="docs/gallery/breakdancing.gif" alt="Animated Clawd: Breakdance" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Happy confetti</strong><br><code>confetti_happy</code><br><img src="docs/gallery/confetti_happy.gif" alt="Animated Clawd: Happy confetti" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Fly a kite</strong><br><code>kite</code><br><img src="docs/gallery/kite.gif" alt="Animated Clawd: Fly a kite" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Pixel stroll</strong><br><code>pixel_walk</code><br><img src="docs/gallery/pixel_walk.gif" alt="Animated Clawd: Pixel stroll" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Skateboard</strong><br><code>skate</code><br><img src="docs/gallery/skate.gif" alt="Animated Clawd: Skateboard" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Take a drive</strong><br><code>car</code><br><img src="docs/gallery/car.gif" alt="Animated Clawd: Take a drive" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Ride a scooter</strong><br><code>scooter</code><br><img src="docs/gallery/scooter.gif" alt="Animated Clawd: Ride a scooter" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Ride a bike</strong><br><code>bike</code><br><img src="docs/gallery/bike.gif" alt="Animated Clawd: Ride a bike" width="300" height="225"></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Float in space</strong><br><code>astronaut</code><br><img src="docs/gallery/astronaut.gif" alt="Animated Clawd: Float in space" width="300" height="225"></td>
    <td align="center" width="33%"><strong>Float in the pool</strong><br><code>pool</code><br><img src="docs/gallery/pool.gif" alt="Animated Clawd: Float in the pool" width="300" height="225"></td>
    <td aria-hidden="true"></td>
  </tr>
</table>
<!-- END ANIMATION GALLERY -->

The 320 × 240 GIFs total about 2.30 MiB and are documentation assets only; the Pi does not load them. To regenerate them and print the three-column table:

```sh
.venv/bin/pip install -e '.[gallery]'
.venv/bin/python tools/render_gallery.py --print-markdown
```


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

curl --get http://127.0.0.1:8765/api/react \
  --data-urlencode 'mood=cloud_engineering' \
  --data-urlencode 'text=Hello, Cloud Engineering!' \
  --data-urlencode 'duration=12'
```

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Public JSON liveness response. |
| `GET /api/state` | Current snapshot: `state`, `elapsed`, `message`, `message_remaining`, `caption`, `caption_remaining`. |
| `POST /api/event` | Any action listed below; optional `duration` in seconds, positive and at most 3600. Omit duration for the action default. |
| `POST /api/message` | `text`: 1–280 Unicode characters; required `duration`: positive seconds, at most 3600. |
| `GET /api/react?mood=wave&text=Hello!` | Atomically select a reaction and show text **above Clawd**; optional `duration`, default 8 seconds, positive and at most 3600. |
| `POST /hooks/claude` | Claude Code JSON lifecycle payload; recognized events receive HTTP 204 with no decision output. |
| `GET /`, `GET /frame.jpg` | Desktop HTML/JPEG mirror, only when `--preview` is enabled. |

A new event immediately replaces the previous event; expiry returns to idle. An event does not clear an active message. Message expiry reveals the then-current live status, not a saved historical status. This is a single display, with no queue, durable history, multi-session aggregation or guaranteed delivery.

### Reaction + overhead text

`http://127.0.0.1:8765/api/react?mood=wave&text=Hello!` starts the wave and displays “Hello!” above Clawd for eight seconds. `mood` accepts **any name in the reaction table**; `text` must contain 1–280 printable Unicode characters, may include newlines, and must not be blank. Encode query values with `curl --get --data-urlencode` or `URLSearchParams`, especially for spaces, `&`, `+`, `#` and non-ASCII text.

The optional `duration` controls **both** the chosen animation and caption. When it expires, Clawd returns to idle and the caption disappears; an `idle` reaction simply remains idle. Use `duration=12` for the full `closeup` approach, expression and return. A new reaction restarts the animation and replaces the caption. A subsequent `/api/event` or Claude hook clears the caption immediately, so stale text cannot accompany an unrelated action. Bottom `/api/message` notes remain independent. A supplied caption overrides the built-in “Cloud Engineering” title during that reaction.

Text wraps/downscales in a reserved overhead lane; the action is fitted below it rather than hidden under the caption. Long captions use smaller lettering. Font coverage still depends on the device's installed fonts.

Missing, blank, duplicate, unknown, malformed or invalid query values return HTTP 400 **without changing the current reaction, caption or note**. Authentication is the same bearer header as other API routes; never put a token in the URL. This is an intentionally state-changing GET for simple webhook/query integrations: do not embed it in remote images or prefetchable links. Cross-site browser requests and foreign `Origin` headers receive HTTP 403, including in token-free loopback mode. CLI requests and same-origin preview controls are supported. Query text can appear in client/proxy URL history, so do not send secrets.

### Reaction summary

All **62 mood/event names** work with both `POST /api/event` and `GET /api/react`. The duration below applies only to `/api/event` when omitted; `/api/react` defaults to 8 seconds for both reaction and caption. The browser tour uses shorter samples for long-lived statuses.

| Mood / event | Event default | What Clawd does | Artwork |
| --- | --- | --- | --- |
| `idle` | Until replaced | Breathe quietly and blink. | Custom |
| `smile` | 8 s | Smile with stepped happy eyes and a gentle bob; no mouth. | Custom |
| `knock` | 8 s | Tap the screen with a foreshortened side block and glass impact marks; no door. | Custom |
| `waiting` | 60 s | Glance around patiently beside a tiny hourglass. | Custom |
| `coffee` | 12 s | Hold a large steaming mug and blink; no lifting, drinking or mouth. | Custom |
| `reading` | 20 s | Look into an open book: pages face Clawd, covers face the viewer; turn a page. | Custom |
| `lens` | 12 s | Inspect through a large magnifying glass with a magnified eye. | Custom |
| `ok` | 8 s | Raise a side block, nod and show an OK! bubble/check mark; no drawn hand. | Custom |
| `scared` | 8 s | Startle, flee behind the right edge, disappear and return from the left; eyes only. | Custom |
| `phone_ringing` | 10 s | Vibrate in rapid intermittent bursts with motion marks; no audio or phone integration. | Custom |
| `sunglasses` | 12 s | Wear black stepped pixel glasses with white checker highlights. | Custom |
| `deal_with_it` | 10 s | Drop the glasses onto the eyes, bounce, show “Deal with it.” and hold the pose. | Custom |
| `closeup` | 12 s | Approach until only the eyes are visible, look around, smile with the eyes and return. | Custom |
| `heart_eyes` | 10 s | Turn square eyes into pulsing hearts. | Custom |
| `flag_pl` | 12 s | Wave Poland's white-over-red flag using the existing rectangular arm. | Custom |
| `flag_aws` | 12 s | Hold a gently fluttering flag with the official AWS mark. | Custom + AWS mark |
| `flag_shipstation` | 12 s | Hold a gently fluttering flag with the official ShipStation mark. | Custom + ShipStation mark |
| `flag_stamps` | 12 s | Hold a gently fluttering flag with the official Stamps.com mark. | Custom + Stamps.com mark |
| `cloud_engineering` | 12 s | Bounce joyfully with heart eyes and “Cloud Engineering” above the head. | Custom |
| `wave` | 8 s | Wave like the website header, playing forward then backward. | [claude.dev](https://claude.dev/shared/video/clawd-waving.json) |
| `looking` | 12 s | Look around. | [claude.dev](https://claude.dev/shared/video/clawd-looking.json) |
| `walking` | 12 s | Walk using source gait frames 8–23. | [claude.dev](https://claude.dev/shared/video/clawd-walking.json) |
| `bounce` | 8 s | Jump. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Jumping.json) |
| `thinking` | 300 s | Think while work is in progress. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Thinking.json) |
| `laptop` | 12 s | Work on a laptop. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Laptop.json) |
| `phone` | 12 s | Check the phone. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Phone.json) |
| `desktop` | 12 s | Work at a desktop computer. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Desktop.json) |
| `notebook` | 12 s | Take notes. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Notebook.json) |
| `headphones` | 12 s | Wear headphones. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Headphones.json) |
| `watch` | 10 s | Check the watch. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Watch.json) |
| `turning` | 8 s | Turn around. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Turning.json) |
| `sleeping` | 30 s | Take a desk nap. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Snooze.json) |
| `lightbulb` | 10 s | Have a bright idea. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Lightbulb.json) |
| `spark` | 10 s | Make a spark. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Spark.json) |
| `swaying` | 12 s | Sway from side to side. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Swaying.json) |
| `juggling` | 12 s | Juggle. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Juggling.json) |
| `hula_hoop` | 12 s | Play with a hula hoop. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-HulaHoop.json) |
| `bubble` | 12 s | Blow a bubble. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Bubble.json) |
| `fishing` | 12 s | Go fishing. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Fishing.json) |
| `watering` | 12 s | Water a plant. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Watering.json) |
| `berry_picking` | 12 s | Pick berries. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-BerryPicking.json) |
| `blooming` | 12 s | Play the blooming-flower scene. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Blooming.json) |
| `rainbow` | 12 s | Make a rainbow. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Rainbow.json) |
| `rose` | 12 s | Offer a rose. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Rose.json) |
| `heart` | 12 s | Send a heart. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Heart.json) |
| `arcade` | 12 s | Take an arcade-game break. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Arcade.json) |
| `meditating` | 12 s | Meditate. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Meditating.json) |
| `excited` | 10 s | Get excited. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Excited.json) |
| `jumping_happy` | 10 s | Jump happily. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-JumpingHappy.json) |
| `dance` | 12 s | Dance. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Dancing.json) |
| `confetti` | 12 s | Celebrate with confetti. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-Confetti.json) |
| `dancing_happy` | 12 s | Do a happy dance. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-DancingHappy.json) |
| `breakdancing` | 12 s | Breakdance. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-BreakDancing.json) |
| `confetti_happy` | 12 s | Celebrate with happy confetti. | [claude.dev](https://claude.dev/shared/video/acts/Clawd-ConfettiHappy.json) |
| `kite` | 20 s | Fly a kite. | [claude.dev pixel sprites](https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js) |
| `pixel_walk` | 12 s | Take a pixel stroll. | claude.dev pixel sprites |
| `skate` | 12 s | Skateboard. | claude.dev pixel sprites |
| `car` | 12 s | Take a drive. | claude.dev pixel sprites |
| `scooter` | 12 s | Ride a scooter. | claude.dev pixel sprites |
| `bike` | 12 s | Ride a bike. | claude.dev pixel sprites |
| `astronaut` | 12 s | Float in space. | claude.dev pixel sprites |
| `pool` | 12 s | Float in the pool. | claude.dev pixel sprites |

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

[`deploy/pipclock.service`](deploy/pipclock.service) is an **opt-in Linux system service running as the unprivileged user `pipclock`**, with repository files in `/opt/maclock-clawd`. It binds loopback and starts native fullscreen without preview. It is not a portable display-driver installer.

On a system with `useradd`, provision the account and copy your checkout into `/opt/maclock-clawd` (the directory must contain the `pipclock` package):

```sh
sudo useradd --system --user-group --home-dir /opt/maclock-clawd --shell /usr/sbin/nologin pipclock
sudo install -d -o pipclock -g pipclock /opt/maclock-clawd
sudo cp -R . /opt/maclock-clawd/
sudo chown -R pipclock:pipclock /opt/maclock-clawd
```

Run the copy commands from the source checkout, not from `/opt/maclock-clawd` itself. If the account/directory already exists, reuse it instead of recreating it. Provision local tty/seat, DRM/render and input permissions for this account using your OS's actual device ownership and access model. A system service does not automatically inherit an interactive graphical login or its permissions. The correct SDL backend, console ownership, device groups and any systemd drop-ins depend on that setup; this unit intentionally does not guess them, grant root, or claim that enabling it alone produces a display.

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

The macOS regression suite passed **25 behavioral tests**, covering website playback boundaries, independent timers, reaction replacement, atomic rejection, URL decoding, authentication, cross-site request protection and non-decision Claude hooks.

A live native-preview smoke run exercised **all 62 reactions through the query API** and decoded 640 × 480 JPEG frames. It checked caption expiry, independent bottom notes, rejected duplicate queries, blocked cross-site requests and hook interruption. Browser checks exercised the overhead-caption form and verified **62 animated GIFs in 21 three-column rows**. Every GIF frame was decoded and loop timing checked; the README markup matches the gallery generator. Visual keyframes include the five new reactions and captions above raised arms, jumps and closeup eyes. A 280-character caption left the clock/date and bottom note panel unchanged.

The built wheel includes all 43 website atlases, official brand PNGs and the renamed GitHub repository metadata. From an extracted `maclock-clawd` directory, its renderer exercised all 62 actions with and without a 280-character caption. The packaged native CLI also served the query API and a 640 × 480 JPEG, then returned to idle after caption expiry.

The full catalog tour was not run end-to-end. These Mac checks do **not** establish Raspberry Pi performance, display rotation, touchscreen behavior or systemd/seat permissions.
