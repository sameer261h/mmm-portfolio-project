"""Shared placeholder-image generator for ad platforms that require real image assets.

Both Google Performance Max asset groups and Meta ad creatives require at
least one real image -- this project has no real creative, so both
platforms' real-API builders use this to generate an obvious solid-color
placeholder with a text label, not real ad creative.
"""

from __future__ import annotations

import io


def generate_placeholder_image(width: int, height: int, label: str, color: tuple[int, int, int]) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(image)
    draw.multiline_text((20, 20), f"PLACEHOLDER\n{label}\n{width}x{height}", fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
