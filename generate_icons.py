"""
generate_icons.py — run once to produce icon-192.png and icon-512.png
from the ECHO SVG lettermark using Pillow only (no cairosvg required).

We draw the icon programmatically in Pillow so there is no SVG rasteriser
dependency.  The result matches the favicon.svg exactly.

Usage:
    python generate_icons.py
"""
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).parent / "apps" / "core" / "static" / "core" / "icons"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────
DEEP   = (30,  27,  75)   # #1E1B4B
WHITE  = (255, 255, 255)
ACCENT = (192, 132, 252)  # #C084FC

def draw_icon(size: int) -> Image.Image:
    scale = size / 32          # 32 is our design grid
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # ── Rounded-rectangle background ─────────────────────────────────────────
    radius = round(6 * scale)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(*DEEP, 255))

    # ── Letter 'E' using four filled rectangles ───────────────────────────────
    # Vertical stem
    sx, sy   = round(8 * scale), round(7 * scale)
    sw, sh   = round(3 * scale), round(18 * scale)
    d.rectangle([sx, sy, sx + sw, sy + sh], fill=(*WHITE, 255))

    bar_h = max(2, round(3 * scale))

    # Top bar
    d.rectangle([round(8*scale), round(7*scale),
                 round(20*scale), round(7*scale) + bar_h],
                fill=(*WHITE, 255))

    # Mid bar (slightly narrower)
    mid_w   = round(9.5 * scale)
    mid_bar = max(2, round(2.5 * scale))
    d.rectangle([round(8*scale), round(14.5*scale),
                 round(8*scale) + mid_w, round(14.5*scale) + mid_bar],
                fill=(*WHITE, 255))

    # Bottom bar
    d.rectangle([round(8*scale), round(22*scale),
                 round(20*scale), round(22*scale) + bar_h],
                fill=(*WHITE, 255))

    # ── Acoustic arc (approximated with a series of filled ellipses) ──────────
    # Q-bezier from (11,27.5) control (16,30.5) to (21,27.5), scaled.
    # We sample the quadratic bezier and draw thick line segments.
    p0 = (11 * scale, 27.5 * scale)
    p1 = (16 * scale, 30.5 * scale)   # control point
    p2 = (21 * scale, 27.5 * scale)
    stroke_w = max(1, round(1.8 * scale))
    steps = max(24, size // 4)
    prev = None
    for i in range(steps + 1):
        t  = i / steps
        bx = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        by = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        if prev:
            d.line([prev, (bx, by)], fill=(*ACCENT, 255), width=stroke_w)
        prev = (bx, by)
    # Round caps
    for cx, cy in [p0, p2]:
        r = stroke_w / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*ACCENT, 255))

    return img


for sz in (192, 512):
    icon = draw_icon(sz)
    out  = OUTPUT_DIR / f"icon-{sz}.png"
    icon.save(out, "PNG", optimize=True)
    print(f"  [OK] {out} ({sz}x{sz})")

print("Done — icons written to", OUTPUT_DIR)
