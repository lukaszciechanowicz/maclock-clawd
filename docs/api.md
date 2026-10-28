# API

[Back to README](../README.md) · [Animation gallery](gallery.md) · [Claude Code integration](claude-code.md)

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
| `POST /api/message` | Timed text above Clawd, replacing the clock: 1–280 Unicode characters; required `duration`: positive seconds, at most 3600. |
| `GET /api/react?mood=wave&text=Hello!` | Atomically select a reaction and show text **above Clawd**; optional `duration`, default 8 seconds, positive and at most 3600. |
| `POST /hooks/claude` | Claude Code JSON lifecycle payload; recognized events receive HTTP 204 with no decision output. |
| `GET /`, `GET /frame.jpg` | Desktop HTML/JPEG mirror, only when `--preview` is enabled. |

A new event immediately replaces the previous event; expiry returns to idle. An event does not clear an active message. The display has one plain header above Clawd: a reaction caption takes priority over a timed message, then any built-in action title, then the hours-and-minutes clock. A message hidden behind a caption keeps its independent expiry timer and reappears only if it is still active when the caption clears. There is no bottom panel or date. This is a single display, with no queue, durable history, multi-session aggregation or guaranteed delivery.

## Reaction + overhead text

`http://127.0.0.1:8765/api/react?mood=wave&text=Hello!` starts the wave and displays “Hello!” above Clawd for eight seconds. `mood` accepts **any name in the reaction table**; `text` must contain 1–280 printable Unicode characters, may include newlines, and must not be blank. Encode query values with `curl --get --data-urlencode` or `URLSearchParams`, especially for spaces, `&`, `+`, `#` and non-ASCII text.

The optional `duration` controls **both** the chosen animation and caption. When it expires, Clawd returns to idle and the caption disappears; an `idle` reaction simply remains idle. Use `duration=12` for the full `closeup` approach, expression and return. A new reaction restarts the animation and replaces the caption. A subsequent `/api/event` or Claude hook clears the caption immediately, so stale text cannot accompany an unrelated action. Timed `/api/message` text remains independent and uses the same header only when no reaction caption is active. Supplied API text overrides the built-in action title.

Text wraps/downscales in a reserved overhead lane, replacing the clock rather than covering Clawd. The artwork stays the same enlarged size with and without text. Long captions use smaller lettering. Font coverage still depends on the device's installed fonts; the seven-segment clock itself needs no font file.

Missing, blank, duplicate, unknown, malformed or invalid query values return HTTP 400 **without changing the current reaction, caption or note**. Authentication is the same bearer header as other API routes; never put a token in the URL. This is an intentionally state-changing GET for simple webhook/query integrations: do not embed it in remote images or prefetchable links. Cross-site browser requests and foreign `Origin` headers receive HTTP 403, including in token-free loopback mode. CLI requests and same-origin preview controls are supported. Query text can appear in client/proxy URL history, so do not send secrets.

## Reaction summary

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

## Authentication and request limits

All POSTs require `Content-Type: application/json`; bodies are limited to 16 KiB and malformed input is rejected. There is no CORS support. For authentication, set `PIPCLOCK_TOKEN` in the server environment and add `Authorization: Bearer ...` to API/hook requests:

```sh
export PIPCLOCK_TOKEN="$(openssl rand -hex 32)"
.venv/bin/python -m pipclock --headless --preview
# In another terminal, set the same token before making requests:
curl http://127.0.0.1:8765/api/state \
  -H "Authorization: Bearer ${PIPCLOCK_TOKEN}"
```

The token protects `/api/*` and `/hooks/*`, not `/health` or the loopback-only preview. Enter the token into the browser mirror's password field when needed; it is not embedded in HTML. Loopback is not authentication against other processes/users on the same machine.
