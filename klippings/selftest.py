"""Check that a Klippings build has everything it needs, then print "Klippings vX.Y.Z" and exit 0, or list what's missing and exit 1.

Run with `Klippings --self-test` (or `python -m klippings --self-test`). It builds the main window without
showing it, loads the bundled icons, fonts and drag-and-drop library, and makes a text file and a quote image
from a made-up sample in a temporary folder. It never shows a dialog, goes online or writes beside the app.
"""

import io
import os
import shutil
import sys
import tempfile

SAMPLE = (
    "The Quiet Orchard (Mara Lind)\n"
    "- Your Highlight on page 12 | Location 180-182 | Added on Monday, 3 March 2025 09:14:02\n"
    "\n"
    "Every tree remembers the winter it survived.\n"
    "==========\n"
)


def say(text):
    """Print only when there is a console; a windowed Windows build has none"""
    stream = sys.stdout
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except (OSError, ValueError):
        pass


def check_bundled_files(problems):
    from klippings.gui import asset_path
    for name in ("klippings.ico", "klippings.png"):
        if not os.path.isfile(asset_path(os.path.join("icon", name))):
            problems.append(f"Icon file missing: {name}")


def check_fonts_and_images(problems):
    from klippings import images
    fonts = images.list_fonts()
    if not fonts:
        problems.append("No quote image fonts found")
        return
    for name, path in fonts.items():
        try:
            font = images.ImageFont.truetype(path, images.FONT_SIZE)
            attribution_font = images.ImageFont.truetype(path, images.ATTRIBUTION_FONT_SIZE)
            lines = images.layout_pages("Every tree remembers the winter it survived.", font)[0]
            image = images.draw_image(font, attribution_font, lines, "Mara Lind")
            image.save(io.BytesIO(), format="WEBP", quality=images.WEBP_QUALITY)
        except Exception as error:
            problems.append(f"Font {name} can't make a quote image: {error}")


def check_export(problems, work):
    from klippings.exporter import export_books
    from klippings.parser import parse_clipping_files
    source = os.path.join(work, "My Clippings.txt")
    with open(source, "w", encoding="utf-8") as file:
        file.write(SAMPLE)
    books, _ = parse_clipping_files([source])
    if len(books) != 1:
        problems.append(f"Sample clippings gave {len(books)} books, expected 1")
        return
    results = export_books(books, os.path.join(work, "out"))
    if len(results) != 1 or not os.path.isfile(results[0][2]):
        problems.append("Sample text file was not written")


def check_window(problems):
    from klippings import gui
    if gui.TkinterDnD is None:
        problems.append("Drag and drop library (tkinterdnd2) can't be loaded")
    app = gui.KindleHighlightsGUI()
    try:
        app.root.withdraw()
        app.root.update_idletasks()
    finally:
        app.closing = True
        (app._tk_root or app.root).destroy()


def run():
    """Run every check and return the exit code"""
    problems = []
    work = tempfile.mkdtemp(prefix="klippings-self-test-")
    try:
        for check in (check_bundled_files, check_fonts_and_images, lambda p: check_export(p, work), check_window):
            try:
                check(problems)
            except Exception as error:
                problems.append(f"{type(error).__name__}: {error}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    from klippings._version import __version__
    for problem in problems:
        say(f"FAIL {problem}")
    if problems:
        say("Self-test failed")
        return 1
    say(f"Klippings v{__version__}")
    return 0
