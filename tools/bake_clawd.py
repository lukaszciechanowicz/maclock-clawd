"""Bake the public website's motion data into offline, native-size PNG atlases.

Developer tool only: pip install '.[artwork]' and playwright install chromium.
Public availability is not an artwork license; review upstream rights before
redistributing. No downloaded JavaScript is evaluated outside a browser.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipclock.catalog import BASE, WEBSITE_ACTIONS

PIXEL_SOURCE = "https://claude.dev/_next/static/chunks/3o01xgcny9qbw.js"
PIXEL_KEYS = ("walk", "skate", "car", "scooter", "bike", "astronaut", "pool", "kite")
VENDOR = "https://claude.dev/shared/vendor/lottie_canvas.min.js"

FETCH = """async urls => {
  const results={};let next=0;
  async function worker(){while(next<urls.length){const url=urls[next++];const response=await fetch(url);if(!response.ok)throw Error(url+': HTTP '+response.status);results[url]=await response.text();}}
  await Promise.all(Array.from({length:4},worker));return results;
}"""


def decode_pixel_packs(source):
    # These are data-only object literals, not code: parse with JSON after
    # quoting their simple keys. Never eval the downloaded module.
    literals = re.findall(r"n\((\{w:\d+,h:\d+,fps:\d+,palette:\[.*?deltas:\[.*?\]\})\)", source)
    if len(literals) != len(PIXEL_KEYS):
        raise ValueError("Upstream pixel data format changed; inspect the source before rebaking")
    return {
        key: json.loads(re.sub(r'([,{])(\w+):', r'\1"\2":', literal))
        for key, literal in zip(PIXEL_KEYS, literals)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-executable", help="optional existing Chromium/Chrome binary")
    parser.add_argument("--output", type=Path, default=ROOT / "pipclock" / "assets")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    urls = [BASE + entry["file"] for entry in WEBSITE_ACTIONS.values() if entry["file"]]
    urls += [PIXEL_SOURCE, VENDOR]
    render = (ROOT / "tools" / "render_clawd.js").read_text()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.browser_executable)
        context = browser.new_context(device_scale_factor=1)
        page = context.new_page()
        # Site-origin browser requests work where an unauthenticated urllib
        # client can be rejected by the host. The Pi never performs this step.
        page.goto("https://claude.dev/", wait_until="domcontentloaded")
        sources = page.evaluate(FETCH, urls)
        pixels = decode_pixel_packs(sources[PIXEL_SOURCE])
        page.goto("about:blank")
        page.add_script_tag(content=sources[VENDOR])
        manifest = {"version": 1, "origin": "https://claude.dev/", "animations": {}}
        for event, entry in WEBSITE_ACTIONS.items():
            pixel = entry["file"] is None
            url = PIXEL_SOURCE if pixel else BASE + entry["file"]
            data = pixels[entry["pixel"]] if pixel else json.loads(sources[url])
            result = page.evaluate(render, {"data": data, "pixel": pixel})
            png = base64.b64decode(result.pop("png"))
            filename = event + ".png"
            (args.output / filename).write_bytes(png)
            result.update({"file": filename, "source": url, "source_sha256": hashlib.sha256(sources[url].encode()).hexdigest()})
            for key in ("mode", "loop"):
                if key in entry:
                    result[key] = entry[key]
            manifest["animations"][event] = result
            print(f"{event}: {result['frames']} frames, {len(png):,} bytes PNG, {result['decoded_bytes']:,} bytes decoded", flush=True)
        browser.close()
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Baked {len(manifest['animations'])} animations to {args.output}", flush=True)


if __name__ == "__main__":
    main()
