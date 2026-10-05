#!/usr/bin/env python3
"""ascii.svg portrait generator.

Pushes a photo through a character ramp and renders it as a self-contained
SVG grid (no scripts, no third-party loads, SMIL-only animation).

    python scripts/make_portrait.py --input assets/portrait.jpg --output ascii.svg

If --input is missing, a procedural placeholder is rendered so the README
still looks intentional until a real photo is added.

The grid assumes an advance width of exactly 0.600em, so the used glyphs of
JetBrains Mono are subset + inlined as base64 (see embed_font). Without that,
a viewer whose default monospace is narrower would see the portrait squeezed.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    print("Pillow is required: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

RAMP = " .:-=+*#%@"
OUT_WIDTH_PX = 460
ADVANCE_EM = 0.600


def embed_font(chars: str, font_path: str | None) -> str:
    """Return an @font-face CSS block subset to *chars*, or '' if unavailable."""
    if not font_path or not os.path.exists(font_path):
        return ""
    try:
        data = open(font_path, "rb").read()
        # Try to subset with fontTools so the SVG stays small.
        try:
            from fontTools import subset

            opts = subset.Options()
            opts.flavor = None
            font = subset.load_font(font_path, opts)
            ss = subset.Subsetter(opts)
            ss.populate(text=chars)
            ss.subset(font)
            buf = io.BytesIO()
            font.save(buf)
            data = buf.getvalue()
        except Exception:
            pass  # fall back to embedding the full file
        b64 = base64.b64encode(data).decode("ascii")
        return (
            "@font-face{font-family:'JetBrains Mono';"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
            "font-weight:400;font-style:normal;}"
        )
    except Exception as e:  # pragma: no cover
        print(f"warn: font embed skipped: {e}", file=sys.stderr)
        return ""


def load_or_placeholder(path: str | None, cols: int) -> "Image.Image":
    if path and os.path.exists(path):
        return Image.open(path).convert("L")
    # Procedural placeholder: radial face-like silhouette so layout can be reviewed.
    w, h = 320, 400
    img = Image.new("L", (w, h), 18)
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2 - 20
    for r in range(150, 0, -1):
        v = int(20 + 180 * (1 - r / 150) ** 1.6)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=v)
    d.ellipse([cx - 90, cy - 110, cx + 90, cy + 40], fill=200)  # face
    d.ellipse([cx - 55, cy - 60, cx - 15, cy - 20], fill=40)  # eyes
    d.ellipse([cx + 15, cy - 60, cx + 55, cy - 20], fill=40)
    d.ellipse([cx - 100, cy - 160, cx + 100, cy - 60], fill=90)  # hair
    return img


def image_to_rows(img: "Image.Image", cols: int, ramp: str) -> list[str]:
    # Monospace cells are taller than wide; 0.55 compensates so faces don't stretch.
    ow, oh = img.size
    rows = max(1, int(oh / ow * cols * 0.55))
    img = img.resize((cols, rows), Image.BICUBIC)
    px = img.load()
    n = len(ramp) - 1
    out: list[str] = []
    for y in range(rows):
        line = "".join(ramp[min(n, px[x, y] * n // 256)] for x in range(cols))
        out.append(line.rstrip() or " ")
    return out


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(rows: list[str], font_css: str, title: str) -> str:
    cols = max(len(r) for r in rows)
    font_size = OUT_WIDTH_PX / cols / ADVANCE_EM
    line_h = font_size * 1.0
    pad = 14
    height = pad * 2 + line_h * len(rows)
    chars = "".join(sorted(set("".join(rows))))

    style = (
        f"{font_css}"
        f"text{{font-family:'JetBrains Mono',monospace;"
        f"font-size:{font_size:.2f}px;line-height:1;fill:#e6edf3}}"
        ".bg{fill:#0d1117}.frame{fill:none;stroke:#21262d;stroke-width:1}"
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{OUT_WIDTH_PX}" '
        f'height="{height:.0f}" viewBox="0 0 {OUT_WIDTH_PX} {height:.0f}" '
        f'role="img" aria-label="{esc(title)}">',
        f"<title>{esc(title)} — ASCII portrait</title>",
        f"<style>{style}</style>",
        f'<rect class="bg" width="{OUT_WIDTH_PX}" height="{height:.0f}" rx="8"/>',
    ]
    y = pad + font_size * 0.85
    for i, row in enumerate(rows):
        # Staggered SMIL fade-in; GitHub strips <script> but keeps SMIL.
        begin = f"{min(2.0, i * 0.02):.2f}s"
        full = esc(row.ljust(cols))
        parts.append(
            f'<text x="{pad}" y="{y:.1f}" xml:space="preserve">{full}'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="0.8s" begin="{begin}" fill="freeze"/></text>'
        )
        y += line_h
    parts.append(
        f'<rect class="frame" x="0.5" y="0.5" width="{OUT_WIDTH_PX - 1}" '
        f'height="{height - 1:.0f}" rx="8"/>'
    )
    parts.append(f"<!-- ramp chars: {esc(chars)} | advance {ADVANCE_EM}em -->")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="assets/portrait.jpg")
    ap.add_argument("--output", default="ascii.svg")
    ap.add_argument("--cols", type=int, default=88)
    ap.add_argument("--ramp", default=RAMP)
    ap.add_argument("--font", default="scripts/fonts/JetBrainsMono-Regular.ttf")
    ap.add_argument("--title", default="Venkatesh R")
    a = ap.parse_args()

    img = load_or_placeholder(a.input, a.cols)
    rows = image_to_rows(img, a.cols, a.ramp)
    css = embed_font("".join(rows) + "Venkatesh R", a.font)
    svg = build_svg(rows, css, a.title)
    with open(a.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"wrote {a.output} ({len(rows)} rows x {a.cols} cols)")


if __name__ == "__main__":
    main()
