"""Render Electric's icon: ``python tools/make_icon.py [OUT.ico]``.

A real frame (three Electrons, Neon) at 16, 24, 32, 48, 64 and 256 pixels,
stored as PNGs inside one .ico, which Windows has read since Vista. Run by
build.ps1 before PyInstaller; needs nothing beyond what Electric itself needs.
"""

import io
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from electric import snapshot  # noqa: E402
from electric.config import Settings  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 256)
SEED = 61


def main(out):
    off = snapshot.Offscreen()
    settings = Settings(particle_type="Electrons", random_count=False, particle_count=3,
                        palette="Neon", new_palette_each_image=False, band_density=1.6)
    big = snapshot.frame(off, settings, (512, 512), SEED, phase=0.15)
    images = []
    for size in SIZES:
        img = pygame.transform.smoothscale(big, (size, size))
        buf = io.BytesIO()
        pygame.image.save(img, buf, "icon.png")
        images.append((size, buf.getvalue()))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size           # 0 means 256 in an ICO directory
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    Path(out).write_bytes(header + entries + blobs)
    print(f"{out}: {', '.join(str(s) for s in SIZES)} px")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "electric.ico")
