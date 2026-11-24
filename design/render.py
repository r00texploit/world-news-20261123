"""Render design/infographic.html to entry.png with a headless Chrome or Edge, then check it against the gate.

This is a build tool, not part of the entry: main.py only copies the committed entry.png. It needs a Chromium-based
browser and Pillow (pip install pillow):

    python design/render.py            # writes entry.png at the repository root
    python design/render.py --scale 2  # renders at 2x and downsamples, for smoother edges

The browser runs with a throwaway profile under design/build/, so no browser profile of yours is read or changed.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / "infographic.html"
TARGET = ROOT / "entry.png"
BUILD = HERE / "build"

SIDE = 1024  # the gate allows at most 1024 x 1024 pixels
MAX_BYTES = 1024 * 1024  # and at most 1 MiB

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
]


def find_browser() -> str:
    """Return a Chromium-based browser executable: $CHROME_PATH, else the first known one found."""
    configured = os.environ.get("CHROME_PATH")
    candidates = [configured] if configured else BROWSER_CANDIDATES
    for candidate in candidates:
        found = candidate if Path(candidate).is_file() else shutil.which(candidate)
        if found:
            return found
    sys.exit("No Chrome or Edge found: set CHROME_PATH to a Chromium-based browser.")


def screenshot(browser: str, scale: int, out_file: Path) -> None:
    """Screenshot the page at SIDE x SIDE CSS pixels and the given device scale factor."""
    BUILD.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BUILD) as profile:
        command: List[str] = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--user-data-dir=" + profile,
            "--force-device-scale-factor=%d" % scale,
            "--window-size=%d,%d" % (SIDE, SIDE),
            "--virtual-time-budget=2000",
            "--screenshot=" + str(out_file),
            SOURCE.as_uri(),
        ]
        subprocess.run(command, check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not out_file.is_file():
        sys.exit("The browser wrote no screenshot.")


def finish(raw_file: Path, scale: int, target: Path) -> Image.Image:
    """Flatten the screenshot to RGB at SIDE x SIDE and save it as an optimised PNG."""
    with Image.open(raw_file) as shot:
        expected = (SIDE * scale, SIDE * scale)
        if shot.size != expected:
            sys.exit("Screenshot is %dx%d, expected %dx%d." % (shot.size + expected))
        image = shot.convert("RGB")
    if scale != 1:
        image = image.resize((SIDE, SIDE), Image.LANCZOS)
    image.save(target, format="PNG", optimize=True)
    return image


def report(target: Path) -> None:
    """Print the gate's numbers for the written file and fail if it is over a limit."""
    data = target.read_bytes()
    with Image.open(target) as image:
        image.verify()
    with Image.open(target) as image:
        width, height = image.size
    print("%s: %dx%d, %d bytes, sha256 %s" % (target.name, width, height, len(data), hashlib.sha256(data).hexdigest()))
    if len(data) > MAX_BYTES or width > SIDE or height > SIDE:
        sys.exit("entry.png is over the gate's limits.")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scale", type=int, default=1, choices=(1, 2), help="device scale factor to render at")
    parser.add_argument("--out", type=Path, default=TARGET, help="where to write the PNG (default: entry.png)")
    args = parser.parse_args(argv)

    BUILD.mkdir(exist_ok=True)
    raw_file = BUILD / ("screenshot@%dx.png" % args.scale)
    screenshot(find_browser(), args.scale, raw_file)
    finish(raw_file, args.scale, args.out)
    report(args.out)


if __name__ == "__main__":
    main()
