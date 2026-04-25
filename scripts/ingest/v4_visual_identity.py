from __future__ import annotations

import colorsys
import hashlib


OPERATOR_COLORS = {
    "jr_hokkaido": "#2CB3C9",
    "jr_east": "#249D55",
    "jr_central": "#F77321",
    "jr_west": "#2369C9",
    "jr_shikoku": "#2F7D32",
    "jr_kyushu": "#D81E24",
    "tokyo_metro": "#00A7DB",
    "toei": "#B51E82",
    "keikyu": "#E60012",
    "keio": "#DD0077",
    "keisei": "#005AAA",
    "odakyu": "#0072BC",
    "seibu": "#00A651",
    "tokyu": "#DA0442",
    "tobu": "#0F5CA8",
}


def color_for_operator(operator_id: str) -> str:
    if operator_id in OPERATOR_COLORS:
        return OPERATOR_COLORS[operator_id]
    digest = hashlib.sha1(operator_id.encode("utf-8")).hexdigest()
    hue = int(digest[:6], 16) % 360 / 360
    red, green, blue = colorsys.hls_to_rgb(hue, 0.47, 0.58)
    return f"#{int(red * 255):02X}{int(green * 255):02X}{int(blue * 255):02X}"
