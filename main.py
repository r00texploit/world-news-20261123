"""World news of Monday 23 November 2026 in one image.

The infographic is the entry.png committed beside this file (drawn from design/infographic.html by
design/render.py). This program, standard library only, copies it to /output/entry.png, so every run writes the
same bytes. Outside the grader, MAKEFUN_OUTPUT_DIR stands in for /output:

    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python main.py
"""

import os
import shutil
from pathlib import Path

IMAGE = Path(__file__).resolve().parent / "entry.png"
READABLE_BY_ALL = 0o644  # make.fun collects /output as another user than the one this program runs as


def main() -> None:
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "entry.png"
    shutil.copyfile(IMAGE, target)
    os.chmod(target, READABLE_BY_ALL)  # a strict umask would otherwise leave it 0600, unreadable to the grader


if __name__ == "__main__":
    main()
