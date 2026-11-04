"""Write parsed highlights to one text file per book."""

import os
import re

RAW_DIR_NAME = 'Highlights_by_Book'
MAX_FILE_STEM_LENGTH = 120
RESERVED_FILE_STEMS = {'CON', 'PRN', 'AUX', 'NUL'} | {
    f'{device}{number}' for device in ('COM', 'LPT') for number in range(1, 10)
}


def short_title(book_title):
    """Return the title without its subtitle"""
    return book_title.split(':')[0].strip() or book_title.strip(' :')


def safe_file_stem(title):
    """Make a title safe to use as a file name on any platform"""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title).strip(' .')
    stem = stem[:MAX_FILE_STEM_LENGTH].rstrip(' .')
    if stem.split('.')[0].upper() in RESERVED_FILE_STEMS:
        stem = f'{stem}_'
    return stem or 'Untitled'


def build_file_names(titles):
    """Give each title a unique file name, using the same names on every run"""
    titles = list(titles)
    short_stem_counts = {}
    for title in titles:
        key = safe_file_stem(short_title(title)).casefold()
        short_stem_counts[key] = short_stem_counts.get(key, 0) + 1

    file_names = {}
    used = set()
    for title in titles:
        stem = safe_file_stem(short_title(title))
        if short_stem_counts[stem.casefold()] > 1:
            stem = safe_file_stem(title)

        candidate = stem
        suffix = 2
        while candidate.casefold() in used:
            candidate = f'{stem} ({suffix})'
            suffix += 1
        used.add(candidate.casefold())
        file_names[title] = f'{candidate}.txt'

    return file_names


def format_metadata(page_info, location):
    """Describe where a highlight came from"""
    if page_info and location:
        return f"Your Highlight on {page_info} | location {location}"
    if page_info:
        return f"Your Highlight on {page_info}"
    if location:
        return f"Your Highlight at location {location}"
    return "Your Highlight"


def save_highlights_to_files(books, output_dir=RAW_DIR_NAME, all_titles=None, should_cancel=None):
    """Save highlights to individual book files, returning (title, count, path) for each"""
    os.makedirs(output_dir, exist_ok=True)
    file_names = build_file_names(all_titles if all_titles is not None else books)
    results = []

    for book_title, highlights in books.items():
        if should_cancel and should_cancel():
            break

        file_path = os.path.join(output_dir, file_names[book_title])

        with open(file_path, 'w', encoding='utf-8') as file:
            for i, (highlight_text, author, page_info, location) in enumerate(highlights, start=1):
                file.write(f"{i}. {highlight_text}\n\t<{book_title}>({author}) {format_metadata(page_info, location)}\n\n")

        results.append((short_title(book_title), len(highlights), file_path))

    return results
