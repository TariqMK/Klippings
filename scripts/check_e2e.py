"""End-to-end check of Klippings on made-up sample clippings: parse, text export with and without page details,
and quote images. Works only in a new, empty temporary folder, so it can never touch real files.

Run from the project root, in an environment with Klippings' dependencies installed:
    python scripts/check_e2e.py                      # checks the source
    python scripts/check_e2e.py --app <executable>   # also runs a built app's --self-test
The script uses the standard library only, so it runs the same way on macOS, Windows and Linux.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LONG_PASSAGE = "A long passage that keeps going so the image layout has to split it across more than one picture. " * 12
SAMPLE = (
    "﻿The Quiet Orchard (Mara Lind)\n"
    "- Your Highlight on page 12 | Location 180-182 | Added on Monday, 3 March 2025 09:14:02\n\n"
    "Every tree remembers the winter it survived.\n"
    "==========\n"
    "The Quiet Orchard (Mara Lind)\n"
    "- Your Highlight on page 40 | Location 610-615 | Added on Tuesday, 4 March 2025 21:02:44\n\n"
    f"{LONG_PASSAGE}\n"
    "==========\n"
    "Notes on Small Boats (Pell, Arno)\n"
    "- Your Highlight at location 95-96 | Added on Friday, March 7, 2025 7:30:00 PM\n\n"
    "Café crème, naïve résumé — the sea doesn't care.\n"
    "==========\n"
    "Notes on Small Boats (Pell, Arno)\n"
    "- Your Bookmark at location 120 | Added on Friday, March 7, 2025 7:31:00 PM\n\n\n"
    "==========\n"
)

failures = []


def check(ok, message):
    print(("PASS " if ok else "FAIL ") + message)
    if not ok:
        failures.append(message)


def sha256(path):
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def check_source(work):
    from klippings import exporter, images, parser

    if os.listdir(work):
        sys.exit(f"Refusing to run: {work} is not empty")
    source = os.path.join(work, "My Clippings.txt")
    # Kindles write Windows line endings and a byte order mark
    with open(source, "w", encoding="utf-8", newline="\r\n") as file:
        file.write(SAMPLE)
    before = sha256(source)

    books, _ = parser.parse_clipping_files([source])
    check(list(books) == ["The Quiet Orchard", "Notes on Small Boats"], f"2 books parsed ({list(books)})")
    check(sum(len(h) for h in books.values()) == 3, "3 highlights, bookmark skipped")

    out = os.path.join(work, "out")
    full = exporter.export_books(books, out, with_metadata=True)
    simple = exporter.export_books(books, out, with_metadata=False)
    check(len(full) == 2 and len(simple) == 2, "4 text files written")
    with open(full[0][2], encoding="utf-8") as file:
        check("12" in file.read(), "file with page details has the page number")
    check(all(" (simple)" in os.path.basename(path) for _, _, path in simple), "simple files use the ' (simple)' suffix")
    boats = next(path for _, _, path in simple if "Boats" in path)
    with open(boats, encoding="utf-8") as file:
        check("Café crème, naïve résumé" in file.read(), "accented text kept")

    fonts = images.list_fonts()
    check(len(fonts) > 0, f"bundled fonts found ({', '.join(fonts)})")
    if fonts:
        results = images.export_images(books, out, next(iter(fonts.values())))
        check(sum(count for _, count, _ in results) >= 4, "quote images made, long passage split")
        for _, _, folder in results:
            for path in images.image_files(folder):
                with open(path, "rb") as file:
                    header = file.read(12)
                if not (header[:4] == b"RIFF" and header[8:12] == b"WEBP"):
                    check(False, f"{path} is a WebP image")

    check(sha256(source) == before, "source clippings file unchanged")


def check_app(app):
    result = subprocess.run([app, "--self-test"], capture_output=True, text=True, timeout=300)
    lines = result.stdout.strip().splitlines()
    print("\n".join(lines))
    check(result.returncode == 0, f"built app self-test exit code is 0 (got {result.returncode})")


def main():
    arguments = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arguments.add_argument("--app", help="a built Klippings executable to self-test as well")
    options = arguments.parse_args()

    work = tempfile.mkdtemp(prefix="klippings-e2e-")
    try:
        check_source(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if options.app:
        check_app(options.app)

    print(f"RESULT {'FAIL' if failures else 'PASS'} on {sys.platform}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
