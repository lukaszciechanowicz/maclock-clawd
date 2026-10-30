# API

[Back to README](../README.md) · [Animation gallery](gallery.md) · [Claude Code integration](claude-code.md) · [Raspberry Pi administration](raspberry-pi.md)

## Client setup on this Mac

The deployed Pi accepts ordinary HTTP requests directly over the LAN; **no SSH or sudo is needed**. In a Bash or Zsh terminal, load the existing private token file and choose the destination:

```sh
source "$HOME/Library/Application Support/maclock-clawd/api.env"
export PIPCLOCK_TOKEN
export PIPCLOCK_URL="${PIPCLOCK_URL:-http://192.168.1.57:8765}"
```

Keep that file private (mode `0600`); never print its contents, commit it, or put the token in a URL. `PIPCLOCK_URL` can instead point to a local development server, such as `http://127.0.0.1:8765`. A token-free loopback server does not require sourcing the file; its API accepts requests without a bearer header. All examples below target the configured URL.

`curl -q` must be the first curl option: it ignores `~/.curlrc`, including custom timing/metrics output that would otherwise contaminate JSON. `--fail-with-body` preserves API error JSON and returns a nonzero exit status for HTTP errors.

## Cookbook

### Health and current snapshot

```sh
# Public liveness check; the native Pi normally reports preview: false.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/health"

# Authenticated state, formatted with Python's standard library.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/state" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" | python3 -m json.tool
```

`state` is the **logical mode**, not always the picture on screen. During idle rotation it remains `"idle"` while `animation` might be `"pool"` or `"reading"`. `elapsed` measures logical event time; `animation_elapsed` measures the current pose time (reset at playlist boundaries, except a one-action playlist plays continuously). `message` and `caption` are separate strings or `null`; each has its own `*_remaining`, `*_elapsed` in seconds and `*_text_size` in pixels. No event-remaining field is returned. On startup Clawd waves for eight seconds before entering idle.

### Play an event, then return to idle

```sh
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/event" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"event":"dance","duration":12}'

curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/event" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"event":"idle"}'
```

### Short and scrolling messages

```sh
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/message" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"text":"Cześć! Build finished.","duration":20,"text_size":80}'

curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/message" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"text":"Cloud Engineering: deployment complete.\nTime for coffee, a stretch, and a well-earned break!","duration":60,"text_size":64}'
```

The second example uses a JSON `\n` escape, not a literal newline inside the JSON string. It displays as a space in the single-line ticker. A message replaces the previous message but does not change the animation.

### Choose a mood and caption together

```sh
curl -q --silent --show-error --fail-with-body --get "$PIPCLOCK_URL/api/react" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  --data-urlencode 'mood=cloud_engineering' \
  --data-urlencode 'text=Cześć, Cloud Engineering! Build #42: A+B & ready.' \
  --data-urlencode 'duration=20' \
  --data-urlencode 'text_size=80'
```

Use `--data-urlencode` for each query value; manual concatenation breaks spaces, `+`, `&`, `#` and UTF-8 text. This request changes the animation and caption atomically.

### Retro Windows scenes

Both scenes use user-provided fullscreen backgrounds. They are **visual only**: no crash, restart or OS shutdown occurs.

```sh
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/event" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"event":"windows_bsod","duration":20}'

curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/event" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"event":"windows_shutdown","duration":20}'

# The existing GET route also supports either scene, text and duration.
curl -q --silent --show-error --fail-with-body --get "$PIPCLOCK_URL/api/react" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  --data-urlencode 'mood=windows_shutdown' \
  --data-urlencode 'text=Just pretending!' \
  --data-urlencode 'duration=20'
```

Each selection has **one delayed peek**: hidden for 0–3 seconds, rising at 3–4, blinking/looking around at 4–7, sinking at 7–8, then hidden for the remainder. A duration shorter than 3 seconds expires before the peek; replaying an explicit event resets it. Both event defaults are 20 seconds, while the browser tour/gallery sample each for 10 seconds. Retro scenes suppress the normal clock/body/footer but retain the Wi-Fi indicator and readable top-lane API captions/messages with the same precedence, size and scrolling behavior. Direct API selection is immediate and bypasses automatic rarity.

## Endpoint reference

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Public JSON liveness response. |
| `GET /api/state` | Logical `state`/`elapsed`, visible `animation`/`animation_elapsed`, and independent message/caption text, remaining time, `*_text_size` and `*_elapsed`. |
| `POST /api/event` | Any action listed below; optional `duration` in seconds, positive and at most 3600. Omit duration for the action default. |
| `POST /api/message` | Timed text above Clawd: 1–280 Unicode characters; required `duration`: positive seconds, at most 3600; optional integer `text_size`: 32–96 px, default 64. |
| `GET /api/react?mood=wave&text=Hello!` | Atomically select a reaction and show text **above Clawd**; optional `duration`: default 8 seconds, at most 3600; optional integer `text_size`: 32–96 px, default 64. |
| `GET /api/idle` | Current idle playlist: ordered `actions` and `interval` in seconds. |
| `POST /api/idle` | Replace the nonempty, unique `actions` list and numeric `interval` in the inclusive range 5–3600 seconds. |
| `POST /hooks/claude` | Claude Code JSON lifecycle payload; recognized events receive HTTP 204 with no decision output. |
| `GET /`, `GET /frame.jpg` | Desktop HTML/JPEG mirror, only when `--preview` is enabled. |

A new event immediately replaces the previous event; expiry returns to idle. An event does not clear an active message. The display has one plain header above Clawd: a reaction caption takes priority over a timed message, then any built-in action title, then the hours-and-minutes clock. A message hidden behind a caption keeps its independent expiry timer and reappears only if it is still active when the caption clears. There is no bottom panel or date. This is a single display, with no queue, durable history, multi-session aggregation or guaranteed delivery.

## Reaction + overhead text

`http://127.0.0.1:8765/api/react?mood=wave&text=Hello!` starts the wave and displays “Hello!” above Clawd for eight seconds. `mood` accepts **any name in the reaction table**; `text` must contain 1–280 printable Unicode characters, may include newlines, and must not be blank. Encode query values with `curl --get --data-urlencode` or `URLSearchParams`, especially for spaces, `&`, `+`, `#` and non-ASCII text.

The optional `duration` controls **both** the chosen animation and caption. When it expires, Clawd returns to the idle playlist and the caption disappears; an `idle` reaction starts the playlist immediately. Use `duration=12` for the full `closeup` approach, expression and return. A new reaction restarts the animation and replaces the caption. A subsequent `/api/event` or Claude hook clears the caption immediately, so stale text cannot accompany an unrelated action. Timed `/api/message` text remains independent and uses the same header only when no reaction caption is active. Supplied API text overrides the built-in action title.

Text uses **64 px by default**, twice the previous maximum font size. Both text endpoints accept optional `text_size`: an integer from **32 through 96**, in logical 640 × 480 display pixels. Fractional values, booleans, null, out-of-range values and JSON strings are rejected. Query-string sizes must be integer text.

Short text stays centered. A line wider than the header enters from the right and scrolls left at 100 px/s, repeating with a 64 px gap. Text is **never shrunk or truncated to fit**; newlines become spaces in the single-line ticker. Choose a long enough `duration` to read the whole line—the timer is not automatically extended. Each message/caption has its own scroll clock; action changes and idle rotation do not reset it, and a hidden message's timer and scrolling continue behind a caption.

The artwork keeps the same enlarged size with and without text. Font coverage still depends on the device's installed fonts; the clock uses its bundled DSEG7 Classic font and needs no system font installation.

Missing, blank, duplicate, unknown, malformed or invalid query values return HTTP 400 **without changing the current reaction, caption or note**. Authentication is the same bearer header as other API routes; never put a token in the URL. This is an intentionally state-changing GET for simple webhook/query integrations: do not embed it in remote images or prefetchable links. Cross-site browser requests and foreign `Origin` headers receive HTTP 403, including in token-free loopback mode. CLI requests and same-origin preview controls are supported. Query text can appear in client/proxy URL history, so do not send secrets.

## Idle playlist

Idle is a logical mode, not necessarily the standard standing pose. The default group has **11 entries**, with 30 seconds per selection:

`idle`, `pool`, `skate`, `headphones`, `sleeping`, `reading`, `coffee`, `kite`, `swaying`, `windows_bsod`, `windows_shutdown`.

Configure any nonempty list of distinct names from the reaction table. Membership controls eligibility: an omitted retro action never appears automatically. Automatic rotation uses a fixed **10:1 per-entry weight**: each selected normal entry appears ten times per cycle and each selected retro entry once, interleaved over ten normal passes. The first configured entry stays first. All-normal groups retain ordered round-robin rotation; retro-only groups alternate equally; one-entry groups play continuously. These weights are built in, not API configuration fields.

```sh
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/idle" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN"

# Replace the entire playlist with the default 11-entry group.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/idle" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"actions":["idle","pool","skate","headphones","sleeping","reading","coffee","kite","swaying","windows_bsod","windows_shutdown"],"interval":30}'

# Disable rotation, not the display: keep the standing pose continuously.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/idle" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"actions":["idle"],"interval":30}'

# Interrupt an explicit event and start the configured playlist now.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/event" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"event":"idle"}'
```

`GET` and `POST /api/idle` return the configuration directly. `interval` accepts finite numbers from 5 to 3600 seconds, including fractions. A single selected action plays continuously without pose resets; use `{"actions":["idle"],"interval":30}` to keep only the standard standing Clawd.

Explicit events/reactions/hooks interrupt the playlist. Their expiry restarts idle at the first entry; an explicit `idle` event starts it immediately. Messages do not interrupt the playlist. Changing the playlist while idle restarts it immediately; changing it during an explicit action leaves that action and its caption running.

The optional [physical previous/next buttons](raspberry-pi.md#optional-physical-previousnext-buttons) step through this same configured order and wrap without changing or saving it. Each press interrupts the current event/reaction, clears its caption, enters logical idle and restarts pose time and the automatic-rotation interval. While idle it steps from the currently visible entry; an explicit action in the list is also used as the starting entry. For an action outside the list (including the startup wave), next selects the first entry and previous selects the last. A one-entry list remains valid. Timed messages retain their independent lifetime, text size and scrolling clock. Explicit events/reactions, expiry back into idle and playlist updates reset manual selection. This is local GPIO behavior, not an additional HTTP endpoint; configure membership/order and interval with the existing API above.

Manual previous/next walks each configured entry exactly once in order, **ignoring automatic rarity**. Explicit API events/reactions also bypass weights and play immediately. The idle API schema remains only `actions` and `interval`; no weight field or new endpoint is needed.

`GET /api/state` keeps `state: "idle"` throughout rotation. Read `animation` for the visible Clawd and `animation_elapsed` for its current pose time. `elapsed` remains logical event time; `message_elapsed` and `caption_elapsed` track their respective text independently.

On the native Pi service, configuration is saved atomically in `/var/lib/pipclock/idle.json`, under the private systemd state directory, and loaded after restarts. Desktop previews are in-memory unless `PIPCLOCK_IDLE_CONFIG` names a settings file. Invalid persisted configuration fails startup explicitly. Invalid requests return HTTP 400 without mutation; a persistence failure returns HTTP 500 and keeps the previous configuration.

Existing saved groups are not silently expanded at startup. To enable the new scenes for an existing installation, append their names through `POST /api/idle`, preserving the other entries and interval.

The preview also exposes text-size controls and an idle-group picker. Only the playlist configuration persists: events, messages, captions, elapsed times and the current playlist position do not survive a process restart. Playlist entries use the configured interval, **not** their event-default durations.


## Reaction summary

All **64 mood/event names** work with both `POST /api/event` and `GET /api/react`. The duration below applies only to `/api/event` when omitted; `/api/react` defaults to 8 seconds for both reaction and caption. The browser tour uses shorter samples for long-lived statuses.

| Mood / event | Event default | What Clawd does | Artwork |
| --- | --- | --- | --- |
| `idle` | Until replaced | Run the configured idle playlist; the `idle` entry itself breathes quietly and blinks. | Custom + selected artwork |
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
| `windows_bsod` | 20 s | User-provided blue-screen background with one delayed Clawd peek; visual only. | User-provided Windows-reference PNG |
| `windows_shutdown` | 20 s | User-provided shutdown background with one delayed Clawd peek; no OS shutdown. | User-provided Windows-reference PNG |

The lens is theatrical animation only: **no camera, microphone or room sensing**. Explicit actions replay when sent again; repeated `thinking` events instead extend the watchdog without resetting its motion. The scared sequence repeats within its active duration; its default duration includes a complete exit and return. `deal_with_it` drops its glasses once per event and holds the result rather than repeatedly dropping them. Unknown event names receive HTTP 400; there are no compatibility aliases for removed actions.

An omitted or JSON `null` event duration selects its table default. Explicit numeric durations must be greater than zero and at most 3600 seconds; fractions are allowed, but booleans and numeric strings are not. For `idle`, a supplied duration is validated but does not stop the playlist. Reacting with `mood=idle` starts the playlist immediately while keeping the caption for its requested duration.

Blank text and control characters other than newlines are rejected. Unicode glyph coverage depends on locally installed fonts; missing scripts or emoji may display replacement boxes.

## Standard-library Python client

Run the client setup above first: `export PIPCLOCK_TOKEN` is required because a sourced shell variable is not necessarily inherited by Python. This example uses only the Python standard library, encodes UTF-8 JSON/query values correctly, and never prints the token:

```sh
python3 - <<'PY'
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

base = os.environ.get("PIPCLOCK_URL", "http://192.168.1.57:8765").rstrip("/")
token = os.environ["PIPCLOCK_TOKEN"]

def request(path, payload=None):
    headers = {"Authorization": "Bearer " + token}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(base + path, data=data, headers=headers)
    try:
        with urlopen(req, timeout=10) as response:
            body = response.read()
            return json.loads(body) if body else None
    except HTTPError as error:
        raise SystemExit(f"HTTP {error.code}: {error.read().decode('utf-8')}")
    except URLError as error:
        raise SystemExit(f"Connection failed: {error.reason}")

print(json.dumps(request("/api/state"), ensure_ascii=False, indent=2))
request("/api/message", {"text": "Cześć z Pythona!", "duration": 30, "text_size": 80})
query = urlencode({"mood": "wave", "text": "Hello + cześć & welcome!",
                   "duration": 12, "text_size": 64})
print(json.dumps(request("/api/react?" + query), ensure_ascii=False, indent=2))
PY
```

## Authentication, limits and errors

All `/api/*` and `/hooks/*` routes require the exact `Authorization: Bearer ...` header when the server has `PIPCLOCK_TOKEN` configured. `/health` is public. A non-loopback bind requires a token; loopback may be token-free, but loopback alone does not protect against other local processes/users. Never send a token in query parameters.

All POSTs require a JSON object and `Content-Type: application/json` (an optional charset is accepted). Bodies must contain 1–16384 bytes; chunked transfer encoding is unsupported. JSON fields not used by the selected endpoint are ignored; `/api/react` instead strictly rejects unknown or duplicate query parameters and requires `mood` and `text`.

| Status | Meaning |
| --- | --- |
| `200` | Successful API request; event/message/react return a snapshot, idle returns the configuration. |
| `204` | Recognized Claude hook accepted, with no response body. |
| `400` | Invalid JSON, fields, action, text, duration, text size, playlist or reaction query; unsupported hook or chunked request. Validation failures do not change the current display/configuration. |
| `401` | Missing or incorrect bearer token. |
| `403` | Cross-origin reaction request rejected. |
| `404` | Unknown route, or preview route when preview is disabled. |
| `408` | Request body timed out (connection timeout is five seconds). |
| `413` | Missing, invalid, zero or oversized body length. |
| `415` | POST content type is not `application/json`. |
| `500` | Idle configuration could not be persisted; previous configuration is retained. |
| `503` | Preview enabled, but its first JPEG is not ready yet. |

There is no CORS support. In particular `/api/react` rejects foreign `Origin` and cross-site fetch headers even in token-free loopback mode. CLI/script/server-to-server requests and same-origin preview controls are supported; remote web pages are not. Reaction query text may appear in URL history, so do not send secrets.

Preview is opt-in (`--preview`) and restricted to loopback binds. Its HTML/JPEG routes are not bearer-protected; the HTML does not embed the API token. Enter the token in its password field when required. The native LAN service has preview disabled; `/` and `/frame.jpg` therefore return 404 rather than exposing a remote mirror. See [Raspberry Pi administration](raspberry-pi.md) for service configuration, deployment, SSH and display diagnostics.

Plain HTTP does **not** encrypt tokens or text. Use only a trusted LAN; do not forward port 8765 from the Internet. Use an encrypted connection on untrusted networks.

### Troubleshooting from the Mac

```sh
# Check reachability without involving authentication.
curl -q --silent --show-error --fail-with-body --connect-timeout 5 "$PIPCLOCK_URL/health"

# Deliberately omit authentication: the deployed Pi should return HTTP 401.
curl -q --silent --show-error --include "$PIPCLOCK_URL/api/state"

# Now authenticate; do not use curl -v or shell tracing with private headers.
curl -q --silent --show-error --fail-with-body "$PIPCLOCK_URL/api/state" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN"
```

- **curl error 7 (failed to connect):** no HTTP response was received. Check the Pi's current IP, port, LAN/Wi-Fi reachability and whether its service is listening. A wrong token cannot cause connection refusal. Use the host administration guide for service-side investigation.
- **HTTP 401:** the server is reachable, but the token is missing or does not match. Re-source the private client file in this terminal; ensure it matches the service's private token through the documented administration process, without printing either secret.
- **HTTP 400:** read the returned `error` JSON; check action spelling, required duration for messages, integer text size and encoded query parameters.
- **JSON followed by timing/metrics:** ensure `-q` is the first curl option; it disables custom `~/.curlrc` output.
- **Text expires before the full line passes:** increase duration (up to 3600 seconds), or shorten the text. Scrolling never extends expiry.
- **Healthy API but blank panel:** liveness is not a display scanout test; use the Pi guide's display/service diagnostics.
