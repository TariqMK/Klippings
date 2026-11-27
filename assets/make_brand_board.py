"""Renders a brand board (copied from the tariq-project-standards skill, run by make_assets.py): one image that shows a project's whole brand, in a fixed designer layout.

Usage (needs PySide6; any Python 3.10+):
  python make_brand_board.py brand.json --out assets/brand-board.png

The board is 1600 x 1250 px, saved at 2x (3200 x 2500). It shows, top to bottom:
  - the primary lockup (icon, name, tagline) and the icon at 80/48/32/16 px on dark and light
  - the palette: the accent, the neutrals of each theme, and the contrast of each text colour on its background
  - typography (the UI and monospace fonts) and the palette applied to a small sample window in each theme

brand.json (paths are relative to the JSON file; "light", "semantic", "icon_small", "subtitle" are optional):
  {
    "name": "PhotoTidy",
    "tagline": "Every photo, in date order.",
    "subtitle": "v1.4 · November 2026",
    "icon": "icon/phototidy.svg",
    "icon_small": "icon/phototidy-small.svg",
    "fonts": {"ui": ["Segoe UI", "Inter"], "mono": ["Cascadia Mono", "Consolas"]},
    "accent": "#3b82f6",
    "semantic": {"success": "#22c55e", "warning": "#f59e0b", "error": "#ef4444"},
    "themes": {
      "dark":  {"bg": "#0f0f10", "surface": "#18181b", "border": "#2a2a2e",
                "text": "#ededed", "text_secondary": "#a1a1a6", "text_muted": "#6e6e73"},
      "light": {"bg": "#ffffff", "surface": "#f5f5f7", "border": "#e2e2e6",
                "text": "#1d1d1f", "text_secondary": "#55555a", "text_muted": "#86868b"}
    }
  }

Every colour comes from the JSON, so the board always matches the app. The layout is fixed: change the
constants below only to change it for every project.
"""

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontInfo,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtSvg import QSvgRenderer

WIDTH, HEIGHT, SCALE = 1600, 1250, 2
MARGIN, GUTTER, PAD, RADIUS = 56, 20, 28, 16
SANS = ["Segoe UI", "Inter", "SF Pro Display", "Helvetica Neue", "Arial"]
MONO = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"]
NEUTRALS = [
    ("bg", "Background"),
    ("surface", "Surface"),
    ("border", "Border"),
    ("text", "Text"),
    ("text_secondary", "Text secondary"),
    ("text_muted", "Text muted"),
]
TEXT_TOKENS = {"text", "text_secondary", "text_muted"}


# ---------- colour helpers ----------


def luminance(color: QColor) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.redF())
        + 0.7152 * channel(color.greenF())
        + 0.0722 * channel(color.blueF())
    )


def contrast(a: QColor, b: QColor) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def grade(ratio: float) -> str:
    if ratio >= 7:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3:
        return "AA large"
    return "Below AA"


def on(color: QColor) -> QColor:
    """Black or white, whichever reads better on the colour."""
    white, black = QColor("#ffffff"), QColor("#0a0a0a")
    return white if contrast(color, white) >= contrast(color, black) else black


def alpha(color: QColor, a: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(a)
    return result


# ---------- drawing helpers ----------


class Board:
    def __init__(self, spec: dict, base: Path):
        self.spec = spec
        self.base = base
        self.themes = {k: {t: QColor(v) for t, v in c.items()} for k, c in spec["themes"].items()}
        if "dark" not in self.themes and "light" not in self.themes:
            sys.exit('brand.json needs a "dark" or "light" theme')
        self.accent = QColor(spec["accent"])
        self.semantic = {k: QColor(v) for k, v in spec.get("semantic", {}).items()}
        # The page uses the light theme when there is one; the lockup always uses the darkest theme.
        self.page = self.themes.get("light") or self.themes["dark"]
        self.hero = self.themes.get("dark") or self.themes["light"]
        fonts = spec.get("fonts", {})
        self.ui_families = fonts.get("ui") or SANS
        self.mono_families = fonts.get("mono") or MONO
        self.icon = self._load_icon(spec.get("icon"))
        self.icon_small = self._load_icon(spec.get("icon_small")) or self.icon

        self.image = QImage(WIDTH * SCALE, HEIGHT * SCALE, QImage.Format.Format_ARGB32)
        self.image.fill(self.page["bg"])
        self.p = QPainter(self.image)
        self.p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.p.scale(SCALE, SCALE)

    def _load_icon(self, rel: str | None):
        if not rel:
            return None
        path = (self.base / rel).resolve()
        if not path.exists():
            sys.exit(f"Icon not found: {path}")
        if path.suffix.lower() == ".svg":
            renderer = QSvgRenderer(QByteArray(path.read_bytes()))
            if not renderer.isValid():
                sys.exit(f"Cannot read the SVG icon: {path}")
            return renderer
        image = QImage(str(path))
        if image.isNull():
            sys.exit(f"Cannot read the icon image: {path}")
        return image

    def font(self, mono: bool, px: float, weight=QFont.Weight.Normal) -> QFont:
        families = self.mono_families if mono else self.ui_families
        available = set(QFontDatabase.families())
        f = QFont()
        f.setFamilies([x for x in families if x in available] or families)
        f.setPixelSize(max(1, round(px)))
        f.setWeight(weight)
        return f

    def text(self, x, y, s, font, color, align="left") -> float:
        """Draws s with its baseline at y. Returns the text width."""
        width = QFontMetricsF(font).horizontalAdvance(s)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        self.p.setFont(font)
        self.p.setPen(color)
        self.p.drawText(QPointF(x, y), s)
        return width

    def box(self, rect: QRectF, fill, border=None, radius=RADIUS):
        self.p.setPen(QPen(border, 1) if border is not None else Qt.PenStyle.NoPen)
        self.p.setBrush(fill)
        self.p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        self.p.setBrush(Qt.BrushStyle.NoBrush)

    def draw_icon(self, rect: QRectF, small=False):
        icon = self.icon_small if small else self.icon
        if icon is None:
            return
        if isinstance(icon, QSvgRenderer):
            # Render at the real device size, so small sizes look as they will in the app.
            size = round(rect.width() * SCALE)
            tile = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
            tile.fill(Qt.GlobalColor.transparent)
            tp = QPainter(tile)
            tp.setRenderHint(QPainter.RenderHint.Antialiasing)
            icon.render(tp, QRectF(0, 0, size, size))
            tp.end()
            self.p.drawImage(rect, tile)
        else:
            self.p.drawImage(rect, icon)

    def panel(self, rect: QRectF, title: str):
        self.box(rect, self.page["surface"], self.page["border"])
        self.text(
            rect.x() + PAD,
            rect.y() + PAD + 13,
            title,
            self.font(False, 14, QFont.Weight.DemiBold),
            self.page["text"],
        )

    # ---------- sections ----------

    def header(self, y):
        name_font = self.font(False, 22, QFont.Weight.DemiBold)
        w = self.text(MARGIN, y + 28, self.spec["name"], name_font, self.page["text"])
        self.text(
            MARGIN + w + 10, y + 28, "Brand guidelines", self.font(False, 22), self.page["text_secondary"]
        )
        if self.spec.get("subtitle"):
            self.text(
                WIDTH - MARGIN, y + 27, self.spec["subtitle"], self.font(True, 13), self.page["text_muted"], "right"
            )

    def lockup(self, rect: QRectF):
        t = self.hero
        self.box(rect, t["bg"], t["border"])
        icon_size, gap = 128, 36
        name_font = self.font(False, 68, QFont.Weight.DemiBold)
        tag_font = self.font(True, 19)
        name_w = QFontMetricsF(name_font).horizontalAdvance(self.spec["name"])
        tag_w = QFontMetricsF(tag_font).horizontalAdvance(self.spec.get("tagline", ""))
        text_w = max(name_w, tag_w)
        has_icon = self.icon is not None
        group_w = (icon_size + gap if has_icon else 0) + text_w
        left = rect.x() + (rect.width() - group_w) / 2
        cy = rect.center().y() - 8
        if has_icon:
            self.draw_icon(QRectF(left, cy - icon_size / 2, icon_size, icon_size))
            left += icon_size + gap
        self.text(left, cy + 10, self.spec["name"], name_font, t["text"])
        if self.spec.get("tagline"):
            self.text(left + 3, cy + 48, self.spec["tagline"], tag_font, t["text_secondary"])
        self.text(rect.x() + PAD, rect.bottom() - PAD + 4, "Primary lockup", self.font(True, 12), t["text_muted"])
        self.text(
            rect.right() - PAD,
            rect.bottom() - PAD + 4,
            "Icon · name · tagline",
            self.font(True, 12),
            t["text_muted"],
            "right",
        )

    def icon_sizes(self, rect: QRectF):
        self.panel(rect, "Icon")
        tops = rect.y() + PAD + 36
        tiles = [k for k in ("dark", "light") if k in self.themes]
        tile_w = (rect.width() - 2 * PAD - GUTTER * (len(tiles) - 1)) / len(tiles)
        tile_h = 196
        sizes = [80, 48, 32, 16]
        for i, key in enumerate(tiles):
            t = self.themes[key]
            tile = QRectF(rect.x() + PAD + i * (tile_w + GUTTER), tops, tile_w, tile_h)
            self.box(tile, t["bg"], t["border"], 12)
            spacing = 22
            row_w = sum(sizes) + spacing * (len(sizes) - 1)
            x = tile.x() + (tile.width() - row_w) / 2
            base = tile.y() + 40 + sizes[0]
            for s in sizes:
                if self.icon is not None:
                    self.draw_icon(QRectF(x, base - s, s, s), small=s <= 32)
                self.text(x + s / 2, base + 26, f"{s}", self.font(True, 11), t["text_muted"], "center")
                x += s + spacing
            self.text(tile.x() + 16, tile.bottom() - 16, f"On {key}", self.font(False, 12), t["text_secondary"])
        note_y = tops + tile_h + 30
        f = self.font(False, 13)
        self.text(rect.x() + PAD, note_y, "Smallest size 16 px. Keep clear space of a quarter", f, self.page["text_secondary"])
        self.text(rect.x() + PAD, note_y + 20, "of the icon's width on every side.", f, self.page["text_secondary"])

    def palette(self, rect: QRectF):
        self.panel(rect, "Colour")
        top = rect.y() + PAD + 36
        inner_h = rect.bottom() - PAD - top

        # Accent: the feature swatch.
        acc = QRectF(rect.x() + PAD, top, 280, inner_h - (44 if self.semantic else 0))
        self.box(acc, self.accent, None, 12)
        ink = on(self.accent)
        self.text(acc.x() + 20, acc.y() + 34, "Accent", self.font(False, 17, QFont.Weight.DemiBold), ink)
        self.text(acc.x() + 20, acc.y() + 56, "Actions, focus, the selected item.", self.font(False, 12), alpha(ink, 0.8))
        self.text(acc.x() + 20, acc.y() + 72, "One per view, used sparingly.", self.font(False, 12), alpha(ink, 0.8))
        self.text(acc.x() + 20, acc.bottom() - 42, self.accent.name().upper(), self.font(True, 24, QFont.Weight.Medium), ink)
        rgb = f"RGB {self.accent.red()} {self.accent.green()} {self.accent.blue()}"
        self.text(acc.x() + 20, acc.bottom() - 20, rgb, self.font(True, 12), alpha(ink, 0.8))
        if self.semantic:
            x = acc.x()
            chip_w = (acc.width() - 8 * (len(self.semantic) - 1)) / len(self.semantic)
            for name, c in self.semantic.items():
                chip = QRectF(x, acc.bottom() + 10, chip_w, 34)
                self.box(chip, c, None, 8)
                self.text(chip.x() + 10, chip.y() + 22, name.capitalize(), self.font(False, 12, QFont.Weight.Medium), on(c))
                x += chip_w + 8

        # Neutrals: one row per theme.
        left = acc.right() + 40
        label_w = 56
        keys = [k for k in ("dark", "light") if k in self.themes]
        row_h = (inner_h - 16 * (len(keys) - 1)) / len(keys)
        sw_gap = 12
        sw_w = (rect.right() - PAD - left - label_w - sw_gap * (len(NEUTRALS) - 1)) / len(NEUTRALS)
        block_h = row_h - 44
        for r, key in enumerate(keys):
            t = self.themes[key]
            y = top + r * (row_h + 16)
            self.text(left, y + 20, key.capitalize(), self.font(False, 13, QFont.Weight.Medium), self.page["text_secondary"])
            for i, (token, label) in enumerate(NEUTRALS):
                c = t[token]
                x = left + label_w + i * (sw_w + sw_gap)
                block = QRectF(x, y, sw_w, block_h)
                self.box(block, c, self.page["border"], 10)
                if token in TEXT_TOKENS:
                    ratio = contrast(c, t["bg"])
                    self.text(
                        x + 12, y + block_h - 12, f"{ratio:.1f}:1 {grade(ratio)}", self.font(True, 11, QFont.Weight.Medium), t["bg"]
                    )
                self.text(x, y + block_h + 18, label, self.font(False, 12, QFont.Weight.DemiBold), self.page["text"])
                self.text(x, y + block_h + 35, c.name().upper(), self.font(True, 12), self.page["text_secondary"])

    def typography(self, rect: QRectF):
        self.panel(rect, "Typography")
        top = rect.y() + PAD + 36
        col_w = (rect.width() - 2 * PAD - GUTTER) / 2
        for i, mono in enumerate((False, True)):
            x = rect.x() + PAD + i * (col_w + GUTTER)
            sample = self.font(mono, 88 if not mono else 64, QFont.Weight.DemiBold if not mono else QFont.Weight.Normal)
            self.text(x - 3, top + 92, "Aa" if not mono else "0{}", sample, self.page["text"])
            family = QFontInfo(self.font(mono, 14)).family()
            self.text(x, top + 136, family, self.font(False, 15, QFont.Weight.DemiBold), self.page["text"])
            role = "Interface: names, headings, labels" if not mono else "Taglines, values, code"
            self.text(x, top + 156, role, self.font(False, 12), self.page["text_secondary"])
            y = top + 196
            if not mono:
                for label, weight in (("Regular", QFont.Weight.Normal), ("Medium", QFont.Weight.Medium), ("Semibold", QFont.Weight.DemiBold)):
                    self.text(x, y, label, self.font(False, 16, weight), self.page["text"])
                    y += 26
            else:
                for line in ("0O 1lI {} [] ->", "192.0.2.14", "42 ms  ·  v1.4.0"):
                    self.text(x, y, line, self.font(True, 14), self.page["text"])
                    y += 26
        # Type scale along the bottom.
        scale = [("Display", 68), ("Title", 22), ("Body", 14), ("Caption", 12)]
        y = rect.bottom() - PAD + 4
        x = rect.x() + PAD
        for label, px in scale:
            w = self.text(x, y, f"{label} {px}", self.font(True, 11), self.page["text_muted"])
            x += w + 20

    def mock(self, rect: QRectF, key: str):
        """A small sample window drawn only from the theme's tokens."""
        t = self.themes[key]
        acc = self.accent
        good = self.semantic.get("success", acc)
        self.box(rect, t["bg"], t["border"], 12)
        # Keep the sidebar inside the window's rounded corners.
        self.p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect.adjusted(1, 1, -1, -1), 11, 11)
        self.p.setClipPath(clip)
        # Title bar.
        bar_h = 34
        self.p.setPen(QPen(t["border"], 1))
        self.p.drawLine(QPointF(rect.x() + 1, rect.y() + bar_h), QPointF(rect.right() - 1, rect.y() + bar_h))
        if self.icon is not None:
            self.draw_icon(QRectF(rect.x() + 14, rect.y() + 9, 16, 16), small=True)
        self.text(rect.x() + 38, rect.y() + 22, self.spec["name"], self.font(False, 12, QFont.Weight.DemiBold), t["text"])
        self.text(rect.right() - 14, rect.y() + 22, key.capitalize(), self.font(True, 11), t["text_muted"], "right")
        # Sidebar.
        side = QRectF(rect.x() + 1, rect.y() + bar_h + 1, 126, rect.height() - bar_h - 2)
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(t["surface"])
        self.p.drawRect(side)
        self.p.setPen(QPen(t["border"], 1))
        self.p.drawLine(side.topRight(), side.bottomRight())
        for i, item in enumerate(("Overview", "Activity", "Reports", "Settings")):
            row = QRectF(side.x() + 8, side.y() + 12 + i * 30, side.width() - 16, 26)
            selected = i == 0
            if selected:
                self.box(row, alpha(acc, 0.16), None, 6)
                self.box(QRectF(row.x(), row.y() + 6, 3, 14), acc, None, 1.5)
            self.text(
                row.x() + 14,
                row.y() + 17,
                item,
                self.font(False, 12, QFont.Weight.Medium if selected else QFont.Weight.Normal),
                t["text"] if selected else t["text_secondary"],
            )
        # Content.
        cx, cy = side.right() + 22, side.y() + 34
        cw = rect.right() - 20 - cx
        self.text(cx, cy, "Overview", self.font(False, 18, QFont.Weight.DemiBold), t["text"])
        self.text(cx, cy + 19, "Updated 2 minutes ago", self.font(False, 11), t["text_muted"])
        # Status chip.
        chip_font = self.font(False, 11, QFont.Weight.Medium)
        chip_w = QFontMetricsF(chip_font).horizontalAdvance("Online") + 30
        chip = QRectF(cx + cw - chip_w, cy - 15, chip_w, 22)
        self.box(chip, alpha(good, 0.14), None, 11)
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(good)
        self.p.drawEllipse(QPointF(chip.x() + 11, chip.center().y()), 3.5, 3.5)
        self.text(chip.x() + 20, chip.y() + 15, "Online", chip_font, t["text"])
        # Card with rows.
        card = QRectF(cx, cy + 36, cw, 104)
        self.box(card, t["surface"], t["border"], 8)
        rows = [("Requests", "1,284"), ("Median time", "42 ms"), ("Errors", "0.2 %")]
        for i, (label, value) in enumerate(rows):
            ry = card.y() + 24 + i * 32
            self.text(card.x() + 14, ry + 2, label, self.font(False, 12), t["text_secondary"])
            self.text(card.right() - 14, ry + 2, value, self.font(True, 12), t["text"], "right")
            if i < len(rows) - 1:
                self.p.setPen(QPen(t["border"], 1))
                self.p.drawLine(QPointF(card.x() + 14, ry + 14), QPointF(card.right() - 14, ry + 14))
        # Buttons.
        by = card.bottom() + 16
        btn_font = self.font(False, 12, QFont.Weight.DemiBold)
        primary = QRectF(cx + cw - 76, by, 76, 30)
        self.box(primary, acc, None, 7)
        self.text(primary.center().x(), primary.y() + 19.5, "Run", btn_font, on(acc), "center")
        secondary = QRectF(primary.x() - 86, by, 76, 30)
        self.box(secondary, t["bg"], t["border"], 7)
        self.text(secondary.center().x(), secondary.y() + 19.5, "Export", btn_font, t["text"], "center")
        self.p.restore()

    def themes_panel(self, rect: QRectF):
        self.panel(rect, "Themes")
        top = rect.y() + PAD + 36
        keys = [k for k in ("dark", "light") if k in self.themes]
        w = (rect.width() - 2 * PAD - GUTTER * (len(keys) - 1)) / len(keys)
        for i, key in enumerate(keys):
            self.mock(QRectF(rect.x() + PAD + i * (w + GUTTER), top, w, rect.bottom() - PAD - top), key)

    def render(self) -> QImage:
        content_w = WIDTH - 2 * MARGIN
        y = MARGIN - 8
        self.header(y)
        y += 60
        row1 = 340
        hero_w = round((content_w - GUTTER) * 0.58)
        self.lockup(QRectF(MARGIN, y, hero_w, row1))
        self.icon_sizes(QRectF(MARGIN + hero_w + GUTTER, y, content_w - hero_w - GUTTER, row1))
        y += row1 + GUTTER
        row2 = 340
        self.palette(QRectF(MARGIN, y, content_w, row2))
        y += row2 + GUTTER
        row3 = HEIGHT - MARGIN - y
        type_w = 540
        self.typography(QRectF(MARGIN, y, type_w, row3))
        self.themes_panel(QRectF(MARGIN + type_w + GUTTER, y, content_w - type_w - GUTTER, row3))
        self.p.end()
        return self.image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", help="brand.json describing the name, icon, fonts and palette.")
    parser.add_argument("--out", required=True, help="Output PNG path.")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for key in ("name", "accent", "themes"):
        if key not in spec:
            sys.exit(f'brand.json is missing "{key}"')

    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - Qt needs an application object for fonts.
    board = Board(spec, spec_path.parent)
    image = board.render()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out))
    print(f"Wrote {out} ({image.width()} x {image.height()} px, {out.stat().st_size // 1024} KB)")

    # Report text contrast, so weak colours are caught before the board is shown.
    weak = []
    for key, t in board.themes.items():
        for token in ("text", "text_secondary"):
            ratio = contrast(t[token], t["bg"])
            if ratio < 4.5:
                weak.append(f"{key} {token} {ratio:.1f}:1")
    if weak:
        print("Below 4.5:1 on the background: " + ", ".join(weak))
        return 1
    print("Contrast check passed (text and secondary text at least 4.5:1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
