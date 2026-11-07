"""Build the Klippings brand images from the master SVG icons.

Writes, in assets/icon/:
  klippings.png   1024 x 1024
  klippings.ico   16, 20, 24, 32, 40, 48, 64, 128, 256 px (PNG-encoded)
  klippings.icns  16 to 1024 px, including the @2x sizes
Writes, in assets/:
  banner.png      README banner, 1280 x 320 drawn at 2x (2560 x 640)
  social-card.png GitHub social preview, 1280 x 640, everything 80 px inside each edge
Writes, in docs/ (the GitHub Pages site):
  icon.svg, apple-touch-icon.png (180 px, no transparency), social-card.png

Sizes 32 px and below come from klippings-small.svg; larger sizes from klippings.svg.
The SVGs may use only <rect> (x, y, width, height, rx, fill) and <circle> (cx, cy, r, fill).
The banner uses the app's Windows fonts (Segoe UI Semibold, Consolas), so run it on Windows.

Run from the project root:  python assets/make_assets.py   (needs Pillow)
"""

import io
import os
import shutil
import struct
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFont

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(ASSETS_DIR, "icon")
DOCS_DIR = os.path.join(os.path.dirname(ASSETS_DIR), "docs")
MASTER = os.path.join(ICON_DIR, "klippings.svg")
SMALL = os.path.join(ICON_DIR, "klippings-small.svg")
SMALL_MAX = 32
SUPERSAMPLE = 4
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]

NAME = "Klippings"
TAGLINE = "Turn Kindle clippings into notes and quotes."
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
NAME_FONT = os.path.join(FONT_DIR, "seguisb.ttf")  # Segoe UI Semibold, the app's UI font
TAGLINE_FONT = os.path.join(FONT_DIR, "consola.ttf")  # Consolas, the app's monospace font
# Dark-mode colours from klippings/gui.py
COLOR_BACKGROUND = "#121110"  # COLOR_SIDEBAR, the darkest background
COLOR_BORDER = "#2c2a26"  # COLOR_HAIRLINE
COLOR_TEXT = "#efe9de"
COLOR_TEXT_SECONDARY = "#aaa398"
COLOR_TEXT_MUTED = "#918b80"
COLOR_TILE = "#262421"  # The icon's own tile colour
SUBLINE = "Windows · macOS · Linux"


def render(svg_path, size):
    """Draw the SVG's rects and circles at the given size, with smooth edges"""
    root = ET.parse(svg_path).getroot()
    view = float(root.get("viewBox").split()[2])
    big = size * SUPERSAMPLE
    scale = big / view
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for element in root:
        tag = element.tag.split("}")[-1]
        value = lambda name: float(element.get(name, 0)) * scale
        if tag == "rect":
            x, y = value("x"), value("y")
            box = [x, y, x + value("width") - 1, y + value("height") - 1]
            draw.rounded_rectangle(box, radius=value("rx"), fill=element.get("fill"))
        elif tag == "circle":
            cx, cy, r = value("cx"), value("cy"), value("r")
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=element.get("fill"))
    return image.resize((size, size), Image.LANCZOS)


def icon(size):
    return render(SMALL if size <= SMALL_MAX else MASTER, size)


def add_small_icns_entries(icns_path):
    """Pillow leaves out the 16 px and 32 px (1x) entries, so add them as PNG data.
    The optional table of contents is dropped, because it would no longer list every entry."""
    with open(icns_path, "rb") as file:
        data = file.read()
    entries = []
    position = 8
    while position < len(data):
        length = struct.unpack(">I", data[position + 4:position + 8])[0]
        if data[position:position + 4] != b"TOC ":
            entries.append(data[position:position + length])
        position += length
    for icon_type, size in ((b"icp4", 16), (b"icp5", 32)):
        buffer = io.BytesIO()
        icon(size).save(buffer, "PNG")
        png = buffer.getvalue()
        entries.append(icon_type + struct.pack(">I", len(png) + 8) + png)
    body = b"".join(entries)
    with open(icns_path, "wb") as file:
        file.write(b"icns" + struct.pack(">I", len(body) + 8) + body)


def make_banner(path, scale=2):
    """Icon on the left, name and tagline on the right, centred as one group"""
    width, height = 1280 * scale, 320 * scale
    banner = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=24 * scale,
        fill=COLOR_BACKGROUND, outline=COLOR_BORDER, width=scale,
    )

    icon_size = 176 * scale
    gap = 48 * scale
    line_gap = 20 * scale
    name_font = ImageFont.truetype(NAME_FONT, 96 * scale)
    tagline_font = ImageFont.truetype(TAGLINE_FONT, 24 * scale)
    name_box = draw.textbbox((0, 0), NAME, font=name_font, anchor="ls")
    tagline_box = draw.textbbox((0, 0), TAGLINE, font=tagline_font, anchor="ls")
    text_width = max(name_box[2] - name_box[0], tagline_box[2] - tagline_box[0])

    # Text block runs from the name's cap height, past its descenders, to the tagline's baseline
    cap_height = -name_box[1]
    name_descent = name_box[3]
    tagline_ascent = -tagline_box[1]
    block_height = cap_height + name_descent + line_gap + tagline_ascent
    left = (width - (icon_size + gap + text_width)) // 2
    banner.alpha_composite(icon(icon_size), (left, (height - icon_size) // 2))

    text_left = left + icon_size + gap
    name_baseline = (height - block_height) // 2 + cap_height
    draw.text((text_left - name_box[0], name_baseline), NAME, font=name_font, fill=COLOR_TEXT, anchor="ls")
    tagline_baseline = name_baseline + name_descent + line_gap + tagline_ascent
    draw.text((text_left, tagline_baseline), TAGLINE, font=tagline_font, fill=COLOR_TEXT_SECONDARY, anchor="ls")
    banner.save(path)


def make_social_card(path):
    """GitHub's repo card layout: icon and name on top, tagline and subline centred below"""
    width, height, safe = 1280, 640, 80
    icon_size, icon_top, icon_gap = 168, 150, 40
    card = Image.new("RGBA", (width, height), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(card)

    name_font = ImageFont.truetype(NAME_FONT, 112)
    name_box = draw.textbbox((0, 0), NAME, font=name_font, anchor="ls")
    name_width = name_box[2] - name_box[0]
    left = (width - (icon_size + icon_gap + name_width)) // 2
    card.alpha_composite(icon(icon_size), (left, icon_top))
    cap_height = -draw.textbbox((0, 0), "H", font=name_font, anchor="ls")[1]
    baseline = icon_top + icon_size // 2 + cap_height // 2
    draw.text((left + icon_size + icon_gap - name_box[0], baseline), NAME, font=name_font, fill=COLOR_TEXT, anchor="ls")

    for text, size, color, line_baseline in (
        (TAGLINE, 34, COLOR_TEXT_SECONDARY, 420),
        (SUBLINE, 24, COLOR_TEXT_MUTED, 476),
    ):
        text_font = ImageFont.truetype(TAGLINE_FONT, size)
        draw.text((width // 2, line_baseline), text, font=text_font, fill=color, anchor="ms")

    card = card.convert("RGB")
    background = Image.new("RGB", card.size, COLOR_BACKGROUND)
    left_edge, top_edge, right_edge, bottom_edge = ImageChops.difference(card, background).getbbox()
    if left_edge < safe or top_edge < safe or right_edge > width - safe or bottom_edge > height - safe:
        raise SystemExit("Social card content is outside the 80 px safe area")
    card.save(path)


def copy_to_site():
    """Pages serves only docs/, so the site keeps its own copies of the brand files"""
    if not os.path.isdir(DOCS_DIR):
        return
    shutil.copy(MASTER, os.path.join(DOCS_DIR, "icon.svg"))
    shutil.copy(os.path.join(ASSETS_DIR, "social-card.png"), os.path.join(DOCS_DIR, "social-card.png"))
    # Apple rounds the corners itself, so fill them with the tile colour
    touch = Image.new("RGBA", (180, 180), COLOR_TILE)
    touch.alpha_composite(icon(180))
    touch.convert("RGB").save(os.path.join(DOCS_DIR, "apple-touch-icon.png"))
    print("Copied icon.svg, apple-touch-icon.png and social-card.png to", DOCS_DIR)


def main():
    master = icon(1024)
    master.save(os.path.join(ICON_DIR, "klippings.png"))

    ico_images = [icon(size) for size in ICO_SIZES]
    ico_images[-1].save(
        os.path.join(ICON_DIR, "klippings.ico"),
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=ico_images[:-1],
    )

    icns_images = [icon(size) for size in ICNS_SIZES]
    icns_path = os.path.join(ICON_DIR, "klippings.icns")
    master.save(icns_path, append_images=icns_images[:-1])
    add_small_icns_entries(icns_path)

    print("Wrote klippings.png, klippings.ico and klippings.icns to", ICON_DIR)

    make_banner(os.path.join(ASSETS_DIR, "banner.png"))
    print("Wrote banner.png to", ASSETS_DIR)

    make_social_card(os.path.join(ASSETS_DIR, "social-card.png"))
    print("Wrote social-card.png to", ASSETS_DIR)
    copy_to_site()


if __name__ == "__main__":
    main()
