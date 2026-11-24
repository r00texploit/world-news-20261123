"""Checks for the entry, standard library only.

The grader runs main.py twice in a sandbox with no network and reads /output/entry.png. Its gate takes a whole PNG
or JPEG of at most 1 MiB and 1024 by 1024 pixels. These tests hold the committed image and the program to that:

    python -m unittest discover -s tests -v
"""

import hashlib
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "entry.png"
MAIN = ROOT / "main.py"

MAX_BYTES = 1024 * 1024
MAX_SIDE = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # PNG colour type -> samples per pixel


def read_chunks(data: bytes) -> List[Tuple[bytes, bytes]]:
    """Return [(type, payload)] for every chunk after the signature, failing on a bad length or CRC."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG: bad signature")
    chunks = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated chunk header at byte %d" % pos)
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        payload = data[pos + 8:pos + 8 + length]
        crc_bytes = data[pos + 8 + length:pos + 12 + length]
        if len(payload) != length or len(crc_bytes) != 4:
            raise ValueError("truncated %r chunk" % kind)
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != struct.unpack(">I", crc_bytes)[0]:
            raise ValueError("bad CRC in %r chunk" % kind)
        chunks.append((kind, payload))
        pos += 12 + length
    return chunks


def describe_png(data: bytes) -> Tuple[int, int]:
    """Check that a PNG is whole (every chunk, every row of image data) and return (width, height)."""
    chunks = read_chunks(data)
    kinds = [kind for kind, _ in chunks]
    if kinds[0] != b"IHDR" or kinds[-1] != b"IEND":
        raise ValueError("PNG must start with IHDR and end with IEND, got %r" % kinds)
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if interlace != 0:
        raise ValueError("interlaced PNGs are not checked here")
    row_bytes = 1 + (width * CHANNELS[colour] * depth + 7) // 8
    pixels = zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT"))
    if len(pixels) != height * row_bytes:
        raise ValueError("image data holds %d bytes, header describes %d" % (len(pixels), height * row_bytes))
    if any(pixels[row * row_bytes] > 4 for row in range(height)):
        raise ValueError("a row starts with an unknown filter type")
    return width, height


def run_main(out_dir: Path) -> Path:
    """Run main.py the way a grader run does, with MAKEFUN_OUTPUT_DIR standing in for /output."""
    env = dict(os.environ, MAKEFUN_OUTPUT_DIR=str(out_dir))
    subprocess.run([sys.executable, str(MAIN)], env=env, check=True, timeout=60)
    return out_dir / "entry.png"


class ImageTests(unittest.TestCase):
    def test_image_is_a_whole_png(self) -> None:
        width, height = describe_png(IMAGE.read_bytes())
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_image_is_within_the_gate_limits(self) -> None:
        data = IMAGE.read_bytes()
        width, height = describe_png(data)
        self.assertLessEqual(len(data), MAX_BYTES, "entry.png is over 1 MiB")
        self.assertLessEqual(width, MAX_SIDE)
        self.assertLessEqual(height, MAX_SIDE)

    def test_checker_rejects_a_truncated_png(self) -> None:
        data = IMAGE.read_bytes()
        with self.assertRaises(ValueError):
            describe_png(data[: len(data) // 2])


class ProgramTests(unittest.TestCase):
    def test_main_copies_the_image_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            written = run_main(Path(tmp)).read_bytes()
        self.assertEqual(written, IMAGE.read_bytes())

    def test_two_runs_write_the_same_bytes(self) -> None:
        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                digests.append(hashlib.sha256(run_main(Path(tmp)).read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1])

    @unittest.skipIf(os.name == "nt", "POSIX file modes only")
    def test_output_is_readable_by_every_user(self) -> None:
        # make.fun collects /output as another user than the one the program runs as.
        with tempfile.TemporaryDirectory() as tmp:
            os.umask(0o077)
            try:
                mode = stat.S_IMODE(run_main(Path(tmp)).stat().st_mode)
            finally:
                os.umask(0o022)
        self.assertEqual(mode & 0o444, 0o444, "entry.png must be readable by every user, got %o" % mode)


if __name__ == "__main__":
    unittest.main()
