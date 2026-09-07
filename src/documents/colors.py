"""Color helpers shared by server-side tag creation paths."""

from __future__ import annotations

import random


def _hue2rgb(p: float, q: float, t: float) -> float:
    if t < 0:
        t += 1
    if t > 1:
        t -= 1
    if t < 1 / 6:
        return p + (q - p) * 6 * t
    if t < 1 / 2:
        return q
    if t < 2 / 3:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def _hsl_to_rgb(
    hue: float,
    saturation: float,
    lightness: float,
) -> tuple[float, float, float]:
    """
    Convert HSL in [0, 1] to RGB components in [0, 255].

    Mirrors src-ui/src/app/utils/color.ts hslToRgb.
    """
    if saturation == 0:
        r = g = b = lightness
    else:
        q = (
            lightness * (1 + saturation)
            if lightness < 0.5
            else lightness + saturation - lightness * saturation
        )
        p = 2 * lightness - q
        r = _hue2rgb(p, q, hue + 1 / 3)
        g = _hue2rgb(p, q, hue)
        b = _hue2rgb(p, q, hue - 1 / 3)
    return r * 255, g * 255, b * 255


def _component_to_hex(c: float) -> str:
    """Mirror frontend componentToHex (Math.floor then zero-padded hex)."""
    return f"{int(c):02x}"


def random_color() -> str:
    """
    Random tag color matching the frontend randomColor() helper.

    Uses HSL with random hue, fixed saturation 0.6, and lightness in
    [0.4, 0.8), then converts to #rrggbb.
    """
    r, g, b = _hsl_to_rgb(random.random(), 0.6, random.random() * 0.4 + 0.4)
    return f"#{_component_to_hex(r)}{_component_to_hex(g)}{_component_to_hex(b)}"
