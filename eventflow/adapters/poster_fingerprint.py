from __future__ import annotations

import io

from PIL import Image


def dhash64(image_bytes: bytes) -> int:
    """
    Compute a 64-bit difference hash (dHash) for robust-ish image dedupe.

    - Resizes to 9x8 grayscale
    - Compares adjacent pixels horizontally
    - Packs 64 comparisons into a uint64 (Python int)
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(img.getdata())
    # pixels is length 72 (9*8). Compare x to x+1 for each row.
    out = 0
    bit = 0
    for y in range(8):
        row = pixels[y * 9 : (y + 1) * 9]
        for x in range(8):
            out |= (1 if row[x] > row[x + 1] else 0) << bit
            bit += 1
    return out

