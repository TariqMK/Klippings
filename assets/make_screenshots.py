"""Take the README screenshots and the drag-and-drop GIF from the real Klippings app, using sample clippings.

Writes, in assets/screenshots/:
  main-light.png, main-dark.png                    a book open, page and location on
  images-and-simple-light.png, ...-dark.png        quote images on, page and location off
  several-files-light.png, ...-dark.png            two clippings files combined, details shown
  quote-image.webp                                 one quote image made by the app
Writes, in assets/gifs/:
  drop-a-file.gif                                  a clippings file dropped on the window (dark)

The app runs from source with Klippings-data and every sample file in a temporary folder, so no real
settings, files or paths appear. Only the app's own content is captured, without the system title bar,
at 2x whatever the display's scaling. Works on Windows, macOS and Linux (X11). It needs a screen of at
least 2240 x 1380 px (or 1120 x 690 on a 2x display) and permission to record the screen on macOS.
Keep the window uncovered while it runs (about 30 seconds).

Run from the project root:  python assets/make_screenshots.py   (needs Pillow)
"""

import os
import shutil
import sys
import tempfile

# ---- Values to update by hand -------------------------------------------------------
VERSION = "2.5.6"  # Newest release tag, shown in the header instead of the dev version
# --------------------------------------------------------------------------------------

WINDOW_SIZE = (1120, 660)
SCALE = 2
GIF_WIDTH = 1120          # The GIF is saved at 1x to keep it small; the README shows it at 840
GIF_FPS = 12
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "assets", "screenshots")
GIF_DIR = os.path.join(PROJECT_ROOT, "assets", "gifs")

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

# A second Kindle's file, as (day added, clipping): three highlights already in the first file, with the
# same dates, so Klippings leaves them out as copies, then new highlights and two books only on this Kindle
SECOND_KINDLE = [
    (2, SAMPLE_CLIPPINGS[1]), (4, SAMPLE_CLIPPINGS[3]), (9, SAMPLE_CLIPPINGS[8]),
    (20, ("Walden (Henry David Thoreau)", "Highlight", 98, "1450-1451",
          "Heaven is under our feet as well as over our heads.")),
    (21, ("Middlemarch (George Eliot)", "Highlight", 211, "3360-3361",
          "What do we live for, if it is not to make life less difficult to each other?")),
    (22, ("Middlemarch (George Eliot)", "Highlight", 402, "6420-6420",
          "It is never too late to be what you might have been.")),
    (23, ("Persuasion (Jane Austen)", "Highlight", 230, "3510-3511",
          "You pierce my soul. I am half agony, half hope.")),
]


def write_clippings(path, dated_clippings):
    entries = []
    for day, (title, kind, page, location, text) in dated_clippings:
        added = f"Added on Monday, {day} January 2024 10:00:00"
        entries.append(f"{title}\n- Your {kind} on page {page} | location {location} | {added}\n\n{text}\n==========\n")
    with open(path, "w", encoding="utf-8") as file:
        file.write("".join(entries))


def main():
    temp_home = tempfile.mkdtemp(prefix="klippings-screens-")
    os.environ["USERPROFILE"] = temp_home
    os.environ["HOME"] = temp_home
    output_dir = os.path.join(temp_home, "Documents", "Highlights")  # Short enough to show in full
    os.makedirs(output_dir)
    clippings_path = os.path.join(temp_home, "My Clippings.txt")
    write_clippings(clippings_path, enumerate(SAMPLE_CLIPPINGS, start=1))
    backup_dir = os.path.join(temp_home, "Kindle Paperwhite")
    os.makedirs(backup_dir)
    second_path = os.path.join(backup_dir, "My Clippings.txt")
    write_clippings(second_path, SECOND_KINDLE)

    # Show the release version without touching the source, and keep Klippings-data in the temp folder
    sys.path.insert(0, PROJECT_ROOT)
    import klippings._version
    klippings._version.__version__ = VERSION
    from klippings import gui, settings
    settings.app_folder = lambda *args, **kwargs: temp_home
    gui.messagebox.showwarning = lambda *args, **kwargs: None
    from klippings.images import export_images, list_fonts
    from klippings.parser import parse_clipping_files
    from PIL import Image, ImageGrab

    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)

    # Measure the display's own scaling first. Changing customtkinter's scaling after the window is
    # built brings back widgets that were hidden, so it is set once, before the window exists.
    probe = gui.tk.Tk()
    probe.geometry("200x100+0+0")
    probe.update()
    probe.after(300)
    probe.update()
    box = (probe.winfo_rootx(), probe.winfo_rooty(), probe.winfo_rootx() + 200, probe.winfo_rooty() + 100)
    display_scale = round(ImageGrab.grab(bbox=box, all_screens=True).width / 200, 2) or 1
    probe.destroy()
    print("Display scale:", display_scale)
    gui.ctk.set_widget_scaling(SCALE / display_scale)
    gui.ctk.set_window_scaling(SCALE / display_scale)

    app = gui.KindleHighlightsGUI()
    window = app.root
    window.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}+0+0")
    frames = []

    def grab_window():
        """The window's content area in screen pixels, without the system title bar"""
        window.update()
        left, top = window.winfo_rootx(), window.winfo_rooty()
        box = (left, top, left + window.winfo_width(), top + window.winfo_height())
        return ImageGrab.grab(bbox=box, all_screens=True)

    def clean_edges(image):
        """Cover the system's window edge and rounded corners with the app's own neighbouring pixels"""
        image = image.convert("RGB")
        width, height = image.size
        edge = max(2, round(image.width / WINDOW_SIZE[0]))  # The frame line, in screen pixels
        for y in range(edge):
            image.paste(image.crop((0, edge, width, edge + 1)), (0, y))
            image.paste(image.crop((0, height - edge - 1, width, height - edge)), (0, height - 1 - y))
        for x in range(edge):
            image.paste(image.crop((edge, 0, edge + 1, height)), (x, 0))
            image.paste(image.crop((width - edge - 1, 0, width - edge, height)), (width - 1 - x, 0))
        radius = 24 * edge
        pixels = image.load()
        for corner_x, corner_y in ((radius, height - radius), (width - radius, height - radius)):
            fill = pixels[corner_x, corner_y]
            for y in range(height - radius, height):
                for x in range(corner_x - radius, corner_x + radius):
                    if 0 <= x < width and (x - corner_x) ** 2 + (y - corner_y) ** 2 > (radius - edge) ** 2 \
                            and (x < radius or x >= width - radius):
                        pixels[x, y] = fill
        return image

    def save(name):
        image = clean_edges(grab_window())
        expected = (WINDOW_SIZE[0] * SCALE, WINDOW_SIZE[1] * SCALE)
        if abs(image.width - expected[0]) > 4 or abs(image.height - expected[1]) > 4:
            stop(f"Captured {image.size}, expected {expected}. Is the screen large enough and uncovered?")
        image.resize(expected, Image.LANCZOS).save(os.path.join(SCREENSHOT_DIR, name), optimize=True)
        print("Wrote", name)

    def stop(message):
        print("Stopped:", message)
        finish()
        raise SystemExit(1)

    def set_view(mode, text=True, metadata=True, images=False):
        gui.ctk.set_appearance_mode(mode)
        app.refresh_appearance()
        app.create_text_var.set(text)
        app.with_metadata_var.set(metadata)
        app.create_images_var.set(images)
        app.refresh_export_options()

    def hide_details():
        if app.details_frame.winfo_ismapped():
            app.toggle_details()

    steps = []

    def step(delay):
        """Run the decorated function after a pause, in order"""
        def add(function):
            steps.append((delay, function))
            return function
        return add

    # 1. Screenshots in light and dark
    @step(800)
    def setup():
        app.output_path_var.set(output_dir)
        app.refresh_output_button()
        app.update_export_state()

    for mode in ("light", "dark"):
        @step(1200)
        def main_view(mode=mode):
            set_view(mode)
            app.open_files([clippings_path], "chosen")
            app.select_book("Walden")

        @step(200)
        def main_shot(mode=mode):
            save(f"main-{mode}.png")

        @step(1200)
        def images_view(mode=mode):
            set_view(mode, metadata=False, images=True)

        @step(200)
        def images_shot(mode=mode):
            save(f"images-and-simple-{mode}.png")

        @step(400)
        def several_view(mode=mode):
            set_view(mode)
            app.open_files([clippings_path, second_path], "chosen")
            app.select_book("Walden")

        @step(1200)
        def several_shot(mode=mode):
            save(f"several-files-{mode}.png")
            app.clear_files()

    # 2. The GIF: hover, drop, the books appear, a second book is chosen
    @step(600)
    def gif_start():
        app.clear_files()
        hide_details()
        set_view("dark")

    def record(seconds):
        for _ in range(int(seconds * GIF_FPS)):
            steps.append((int(1000 / GIF_FPS), lambda: frames.append(grab_window())))

    @step(800)
    def gif_ready():
        pass

    record(1.2)
    steps.append((0, lambda: app.show_drop_hover(True)))
    record(1.0)
    steps.append((0, lambda: app.drop_files(type("Drop", (), {"data": window.tk.call("list", clippings_path)})())))
    record(1.5)
    steps.append((0, lambda: app.select_book("Pride and Prejudice")))
    record(1.0)
    steps.append((0, lambda: app.select_book("Frankenstein")))
    record(2.0)

    @step(100)
    def gif_save():
        os.makedirs(GIF_DIR, exist_ok=True)
        width = GIF_WIDTH
        height = round(frames[0].height * width / frames[0].width)
        resized = [clean_edges(frame).resize((width, height), Image.LANCZOS) for frame in frames]
        palette = resized[len(resized) // 2].quantize(colors=128, method=Image.MEDIANCUT)
        images = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in resized]
        durations = [int(1000 / GIF_FPS)] * len(images)
        durations[-1] = 1000  # Rest on the result before looping
        path = os.path.join(GIF_DIR, "drop-a-file.gif")
        images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
        print(f"Wrote drop-a-file.gif ({len(images)} frames, {os.path.getsize(path) / 1_000_000:.1f} MB)")

    @step(100)
    def finish():
        app.closing = True
        app._tk_root.destroy() if app._tk_root else window.destroy()

    def run(index=0):
        if index < len(steps):
            delay, function = steps[index]
            function()
            window.after(steps[index + 1][0] if index + 1 < len(steps) else 0, lambda: run(index + 1))

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    window.attributes("-topmost", True)
    window.after(steps[0][0], run)
    app.run()

    # One quote image, made by the app's own exporter
    books, _ = parse_clipping_files([clippings_path])
    image_dir = os.path.join(temp_home, "images")
    font_path = next(iter(list_fonts().values()))
    export_images({"Walden": books["Walden"][:1]}, image_dir, font_path)
    for folder, _, files in os.walk(image_dir):
        for name in files:
            shutil.copy(os.path.join(folder, name), os.path.join(SCREENSHOT_DIR, "quote-image.webp"))

    shutil.rmtree(temp_home, ignore_errors=True)
    print("Wrote screenshots to", SCREENSHOT_DIR, "and the GIF to", GIF_DIR)


if __name__ == "__main__":
    main()
