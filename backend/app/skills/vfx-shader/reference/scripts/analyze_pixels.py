#!/usr/bin/env python3
"""Sample and compare pixels between reference and rendered images.

Usage: analyze_pixels.py <reference.png> <render.png>
Output: JSON to stdout with per-position RGB + avg_color_distance

Used by codex subagent (Phase 5) for pixel evidence in evaluation.
"""
import sys
import json
from PIL import Image


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: analyze_pixels.py <ref> <render>"}))
        sys.exit(1)

    ref = Image.open(sys.argv[1]).convert("RGB")
    render = Image.open(sys.argv[2]).convert("RGB")

    if ref.size != render.size:
        render = render.resize(ref.size)

    w, h = ref.size
    positions = {
        "tl": (0, 0),
        "tr": (w - 1, 0),
        "bl": (0, h - 1),
        "br": (w - 1, h - 1),
        "center": (w // 2, h // 2),
        "top_mid": (w // 2, 0),
        "bot_mid": (w // 2, h - 1),
        "left_mid": (0, h // 2),
        "right_mid": (w - 1, h // 2),
    }

    result = {}
    total_diff = 0.0
    for name, (x, y) in positions.items():
        r, g, b = ref.getpixel((x, y))
        rr, rg, rb = render.getpixel((x, y))
        diff = (abs(r - rr) + abs(g - rg) + abs(b - rb)) / 3
        total_diff += diff
        result[name] = {
            "reference": [r, g, b],
            "render": [rr, rg, rb],
            "diff": round(diff, 2),
        }

    result["avg_color_distance"] = round(total_diff / len(positions), 2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
