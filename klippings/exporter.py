"""Write parsed highlights to text files, one per book."""

import os
import re

SIMPLE_FILE_SUFFIX = ' (simple)'
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


def build_file_stems(titles):
    """Give each title a unique file name stem, using the same stems on every run"""
    titles = list(titles)
    short_stem_counts = {}
    for title in titles:
        key = safe_file_stem(short_title(title)).casefold()
        short_stem_counts[key] = short_stem_counts.get(key, 0) + 1

    file_stems = {}
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
        file_stems[title] = candidate

    return file_stems


def format_metadata(page_info, location):
    """Describe where a highlight came from"""
    if page_info and location:
        return f"Your Highlight on {page_info} | location {location}"
    if page_info:
        return f"Your Highlight on {page_info}"
    if location:
        return f"Your Highlight at location {location}"
    return "Your Highlight"


def format_with_metadata(book_title, highlights):
    """Format highlights with the book and location under each one"""
    return ''.join(
        f"{i}. {highlight_text}\n\t<{book_title}>({author}) {format_metadata(page_info, location)}\n\n"
        for i, (highlight_text, author, page_info, location) in enumerate(highlights, start=1)
    )


def format_simple(book_title, highlights):
    """Format highlights with separators and no metadata"""
    author = highlights[0][1]
    header_lines = [short_title(book_title), author] if author else [short_title(book_title)]
    numbered = [f"{i}. {highlight[0]}" for i, highlight in enumerate(highlights, start=1)]
    return '\n'.join(header_lines) + '\n\n---\n\n' + '\n\n---\n\n'.join(numbered)


def planned_files(books, output_dir, with_metadata=True, all_titles=None):
    """Work out each book's file as {title: (path, formatter)}"""
    file_stems = build_file_stems(all_titles if all_titles is not None else books)
    suffix, formatter = ('', format_with_metadata) if with_metadata else (SIMPLE_FILE_SUFFIX, format_simple)
    return {
        book_title: (os.path.join(output_dir, f'{file_stems[book_title]}{suffix}.txt'), formatter)
        for book_title in books
    }


def existing_files(books, output_dir, with_metadata=True, all_titles=None):
    """List the files an export would replace"""
    files = planned_files(books, output_dir, with_metadata, all_titles)
    return [path for path, _ in files.values() if os.path.exists(path)]


def export_books(books, output_dir, with_metadata=True, all_titles=None, should_cancel=None):
    """Write a file for each book, returning (title, count, path) for each"""
    os.makedirs(output_dir, exist_ok=True)
    files = planned_files(books, output_dir, with_metadata, all_titles)
    results = []

    for book_title, highlights in books.items():
        if should_cancel and should_cancel():
            break

        path, formatter = files[book_title]
        with open(path, 'w', encoding='utf-8') as file:
            file.write(formatter(book_title, highlights))

        results.append((short_title(book_title), len(highlights), path))

    return results
