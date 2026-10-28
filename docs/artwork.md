# Artwork and attribution

[Back to README](../README.md) · [Animation gallery](gallery.md)

## Source attribution and redistribution

Clawd and the website source artwork remain **copyright Anthropic**. This is an unofficial project, not affiliated with or endorsed by Anthropic. The custom artwork follows user-supplied Clawd references; it is not a claim of original character ownership.

The website sources are published on [claude.dev](https://claude.dev/). Its [interaction script](https://claude.dev/_next/static/chunks/3vrq03-z-93vf.js) supplies the act inventory and header-wave playback behavior; the [sprite data module](https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js) contains kite, walking, skateboard, car, scooter, bike, astronaut and pool frames. The complete selected source-file inventory is linked in the [reaction reference](api.md#reaction-summary) and recorded in [`pipclock/catalog.py`](../pipclock/catalog.py). Header `wave` follows the source's forward-then-backward playback; `walking` uses source frames 8–23 for its gait. Coffee and sunglasses deliberately use the requested custom variants instead of the site's corresponding acts.

Publicly reachable asset URLs **do not establish an open-source or open-content license**. No project license has been selected. Source copyright remains Anthropic's, and character/trademark and asset permissions need review **before public redistribution**, including redistribution of baked or modified frames. Bundling frames does not remove the source rights restrictions.

Flag artwork uses official marks from [AWS](https://aws.amazon.com/), [ShipStation](https://www.shipstation.com/wp-content/uploads/2026/02/logo-ss-primary-rgb-1-1.svg) and [Stamps.com](https://www.stamps.com/wp-content/uploads/2026/02/logo-stamps-primary-rgb-1-1.svg). These marks belong to their respective owners and do not imply sponsorship or endorsement. The native flag animations are custom; the logos are not original project artwork. Source URLs and SHA-256 hashes are recorded in [`pipclock/assets/brands/sources.json`](../pipclock/assets/brands/sources.json). See also the [AWS trademark guidelines](https://aws.amazon.com/trademark-guidelines/).

The clock uses **DSEG7 Classic Regular** by keshikan, bundled unmodified from the [official DSEG v0.46 release](https://github.com/keshikan/DSEG/releases/tag/v0.46). The font is licensed under the **SIL Open Font License 1.1**, with its original copyright and Reserved Font Name notice included in [`DSEG-LICENSE.txt`](../pipclock/assets/fonts/DSEG-LICENSE.txt). This font license is separate from the character artwork rights above.

The existing package, CLI and environment-variable names remain `pipclock` and `PIPCLOCK_TOKEN`; the on-screen character is Clawd.

## Rebuilding the bundled artwork

The runtime needs only pygame, the included PNG artwork and the bundled DSEG clock font. Baking is a separate desktop-only developer task:

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

## Regenerating the gallery

Run from the repository root:

```sh
.venv/bin/pip install -e '.[gallery]'
.venv/bin/python tools/render_gallery.py --print-markdown
```

The exporter regenerates the GIFs and prints categorized, three-column tables for [the gallery document](gallery.md). Replace the content between its `BEGIN ANIMATION GALLERY` and `END ANIMATION GALLERY` markers with that output. Categories, order and labels come directly from the local preview controls in `pipclock/preview.html`. The example clock and connected Wi-Fi icon are fixed for reproducible exports; GIFs are documentation assets and are not loaded by the Pi.
