"""Take the README screenshots from the real Klippings app, using sample clippings.

Writes, in assets/screenshots/:
  main-light.png, main-dark.png                    a book open, page and location on
  images-and-simple-light.png, ...-dark.png        quote images on, page and location off
  quote-image.webp                                 one quote image made by the app

The app runs from source with its home folder pointed at a temporary folder, so no real
settings, files or paths appear. The window is captured at 2x, so this needs Windows and a
screen at least 2240 x 1380 px. Keep the window uncovered while it runs (about 10 seconds).

Run from the project root:  python assets/make_screenshots.py
"""

import ctypes
import os
import shutil
import sys
import tempfile

# ---- Values to update by hand -------------------------------------------------------
VERSION = "2.5.3"  # Newest release tag, shown in the header instead of the dev version
# --------------------------------------------------------------------------------------

WINDOW_SIZE = (1120, 660)
SCALE = 2
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "screenshots")

# Public-domain books, so the sample text is free to show
SAMPLE_CLIPPINGS = [
    ("Walden (Henry David Thoreau)", "Highlight", 12, "171-173",
     "I went to the woods because I wished to live deliberately, to front only the essential facts "
     "of life, and see if I could not learn what it had to teach, and not, when I came to die, "
     "discover that I had not lived."),
    ("Walden (Henry David Thoreau)", "Highlight", 8, "104-104",
     "The mass of men lead lives of quiet desperation."),
    ("Walden (Henry David Thoreau)", "Note", 8, "104", "Compare with Seneca."),
    ("Walden (Henry David Thoreau)", "Highlight", 14, "190-191",
     "Our life is frittered away by detail. Simplify, simplify."),
    ("Walden (Henry David Thoreau)", "Highlight", 52, "702-702",
     "Rather than love, than money, than fame, give me truth."),
    ("Pride and Prejudice (Jane Austen)", "Highlight", 1, "5-6",
     "It is a truth universally acknowledged, that a single man in possession of a good fortune, "
     "must be in want of a wife."),
    ("Pride and Prejudice (Jane Austen)", "Highlight", 47, "702-703",
     "I declare after all there is no enjoyment like reading!"),
    ("Pride and Prejudice (Jane Austen)", "Bookmark", 120, "1840", ""),
    ("Moby-Dick (Herman Melville)", "Highlight", 1, "3-3", "Call me Ishmael."),
    ("Moby-Dick (Herman Melville)", "Highlight", 52, "905-905",
     "It is not down on any map; true places never are."),
    ("Frankenstein (Mary Shelley)", "Highlight", 158, "2511-2511",
     "Beware; for I am fearless, and therefore powerful."),
    ("Frankenstein (Mary Shelley)", "Highlight", 70, "1120-1121",
     "Nothing is so painful to the human mind as a great and sudden change."),
    ("Jane Eyre (Charlotte Bronte)", "Highlight", 255, "4102-4103",
     "I am no bird; and no net ensnares me: I am a free human being with an independent will."),
    ("Jane Eyre (Charlotte Bronte)", "Highlight", 498, "8010-8010", "Reader, I married him."),
    ("A Tale of Two Cities (Charles Dickens)", "Highlight", 1, "2-4",
     "It was the best of times, it was the worst of times, it was the age of wisdom, it was the "
     "age of foolishness."),
]


def write_sample_clippings(path):
    entries = []
    for day, (title, kind, page, location, text) in enumerate(SAMPLE_CLIPPINGS, start=1):
        place = f"location {location}"
        added = f"Added on Monday, {day} January 2024 10:00:00"
        entries.append(f"{title}\n- Your {kind} on page {page} | {place} | {added}\n\n{text}\n==========\n")
    with open(path, "w", encoding="utf-8") as file:
        file.write("".join(entries))


def main():
    temp_home = tempfile.mkdtemp(prefix="klippings-screens-")
    os.environ["USERPROFILE"] = temp_home
    os.environ["HOME"] = temp_home
    output_dir = os.path.join(temp_home, "Documents", "Highlights")  # Short enough to show in full
    os.makedirs(output_dir)
    clippings_path = os.path.join(temp_home, "My Clippings.txt")
    write_sample_clippings(clippings_path)

    # Show the release version without touching the source
    sys.path.insert(0, PROJECT_ROOT)
    import klippings._version
    klippings._version.__version__ = VERSION
    from klippings import gui
    from klippings.images import export_images, list_fonts
    from klippings.parser import parse_clipping_files
    from PIL import ImageGrab

    # Render at exactly 2x, whatever the Windows display scaling is
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    system_scale = ctypes.windll.user32.GetDpiForSystem() / 96
    gui.ctk.set_widget_scaling(SCALE / system_scale)
    gui.ctk.set_window_scaling(SCALE / system_scale)

    app = gui.KindleHighlightsGUI()
    window = app.root
    window.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}+0+0")
    window.attributes("-topmost", True)
    app.output_path_var.set(output_dir)
    app.refresh_output_button()
    app.open_files([clippings_path], "chosen")
    app.select_book("Walden")

    os.makedirs(OUT_DIR, exist_ok=True)
    views = [
        ("main", dict(text=True, metadata=True, images=False)),
        ("images-and-simple", dict(text=True, metadata=False, images=True)),
    ]
    steps = []
    for view, options in views:
        for mode in ("light", "dark"):
            steps.append((view, options, mode))

    def capture(index=0):
        if index == len(steps):
            window.after(100, finish)
            return
        view, options, mode = steps[index]
        gui.ctk.set_appearance_mode(mode)
        app.refresh_appearance()
        app.create_text_var.set(options["text"])
        app.with_metadata_var.set(options["metadata"])
        app.create_images_var.set(options["images"])
        app.refresh_export_options()
        window.after(1200, lambda: grab(index, view, mode))

    def grab(index, view, mode):
        window.update()
        left, top = window.winfo_rootx(), window.winfo_rooty()
        box = (left, top, left + window.winfo_width(), top + window.winfo_height())
        ImageGrab.grab(bbox=box, all_screens=True).save(os.path.join(OUT_DIR, f"{view}-{mode}.png"))
        capture(index + 1)

    def finish():
        app.closing = True
        app._tk_root.destroy() if app._tk_root else window.destroy()

    window.after(1500, capture)
    app.run()

    # One quote image, made by the app's own exporter
    books, _ = parse_clipping_files([clippings_path])
    image_dir = os.path.join(temp_home, "images")
    font_path = next(iter(list_fonts().values()))
    export_images({"Walden": books["Walden"][:1]}, image_dir, font_path)
    for folder, _, files in os.walk(image_dir):
        for name in files:
            shutil.copy(os.path.join(folder, name), os.path.join(OUT_DIR, "quote-image.webp"))

    shutil.rmtree(temp_home, ignore_errors=True)
    print("Wrote screenshots to", OUT_DIR)


if __name__ == "__main__":
    main()
