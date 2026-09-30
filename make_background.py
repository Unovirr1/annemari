"""Generates the tiled page background used by the 1994-95 stylesheet.

No Pillow in this environment, so this writes a small tileable PNG by hand:
zlib + struct + the 5 PNG chunk types.  Run once, output lands in static/.

    .venv/bin/python make_background.py
"""

from __future__ import annotations

import os
import random
import struct
import zlib

W = H = 64
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "space.png")

# Deep navy, the colour every 1994 homepage background was.
BG = (8, 12, 48)
# Two star tints so the tile does not look like TV static.
STARS = [(255, 255, 255), (176, 200, 255), (255, 240, 200)]


def chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def build_pixels(seed: int = 1994) -> list[list[tuple[int, int, int]]]:
    """Stars are placed on a torus so the tile wraps seamlessly."""
    rng = random.Random(seed)
    rows = [[BG for _ in range(W)] for _ in range(H)]

    for _ in range(26):
        x, y = rng.randrange(W), rng.randrange(H)
        colour = rng.choice(STARS)
        bright = rng.random() < 0.25
        pixel = tuple(min(255, c + 60) for c in colour) if bright else colour
        rows[y][x] = pixel
        # A few stars get a cross flare; each neighbour offset also wraps.
        if rng.random() < 0.3:
            for dx, dy in ((1, 0), (0, 1)):
                rows[(y + dy) % H][(x + dx) % W] = tuple(c // 2 for c in pixel)

    # Faint nebula wash, also wrapped, to break up the flat navy.
    for _ in range(9):
        cx, cy = rng.randrange(W), rng.randrange(H)
        tint = rng.choice([(24, 32, 92), (16, 48, 80), (44, 24, 88)])
        radius = rng.randint(3, 7)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                y, x = (cy + dy) % H, (cx + dx) % W
                base = rows[y][x]
                rows[y][x] = tuple(
                    min(255, int(b + (t - b) * 0.45)) for b, t in zip(base, tint)
                )
    return rows


def encode_png(rows: list[list[tuple[int, int, int]]]) -> bytes:
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("3B", *px) for px in row) for row in rows
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as handle:
        handle.write(encode_png(build_pixels()))
    print(f"wrote {OUT} ({W}x{H} tile)")


if __name__ == "__main__":
    main()
