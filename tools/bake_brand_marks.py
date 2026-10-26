"""Bake official header wordmarks into small offline PNGs for Clawd's flags.

Desktop-only tool using the optional artwork dependencies. Logos remain the
trademarks/copyright of their respective owners; this is not a license grant.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "aws": "https://aws.amazon.com/",
    "shipstation": "https://www.shipstation.com/wp-content/uploads/2026/02/logo-ss-primary-rgb-1-1.svg",
    "stamps": "https://www.stamps.com/wp-content/uploads/2026/02/logo-stamps-primary-rgb-1-1.svg",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-executable")
    args = parser.parse_args()
    output = ROOT / "pipclock" / "assets" / "brands"
    output.mkdir(parents=True, exist_ok=True)
    provenance = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.browser_executable)
        context = browser.new_context(device_scale_factor=1)
        page = context.new_page()
        for name, url in SOURCES.items():
            response = context.request.get(url)
            if not response.ok:
                raise RuntimeError(f"{url}: HTTP {response.status}")
            raw = response.text()
            svg = raw
            if name == "aws":
                match = re.search(r'data-testid="(?:mobile-nav-item-logo-link|nav-item-logo-link)".*?(<svg\b.*?</svg>)', raw, re.S)
                if not match:
                    raise ValueError("AWS header logo markup changed")
                svg = match.group(1).replace("viewbox=", "viewBox=")
            page.set_content('<html><body style="margin:0;background:transparent">' + svg + '</body></html>')
            page.locator("svg").evaluate("""svg => {
              const box=svg.viewBox.baseVal;
              svg.setAttribute('width','256');svg.setAttribute('height',String(Math.round(256*box.height/box.width)));
              svg.style.display='block';svg.style.color='#000000';
            }""")
            page.locator("svg").screenshot(path=str(output / (name + ".png")), omit_background=True)
            provenance[name] = {"source": url, "source_sha256": hashlib.sha256(raw.encode()).hexdigest()}
            print(f"Baked {name} from {url}", flush=True)
        browser.close()
    (output / "sources.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
