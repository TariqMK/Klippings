"""Strip metadata from exported highlight files."""

import os
import re

from klippings.exporter import short_title
from klippings.parser import read_file_with_encoding

SIMPLE_DIR_NAME = 'Highlights_by_Book_(Simple)'
METADATA_LINE = re.compile(r'^\t<(.*)>\((.*)\) Your Highlight.*$', re.MULTILINE)


def parse_exported_text(text):
    """Return (book name, author, highlights) from an exported book file"""
    book_name = author = None
    highlights = []
    position = 0

    for match in METADATA_LINE.finditer(text):
        if book_name is None:
            book_name = short_title(match.group(1))
            author = match.group(2).strip()
        highlight = text[position:match.start()].strip()
        if highlight:
            highlights.append(highlight)
        position = match.end()

    return book_name, author, highlights


def format_highlights(book_name, author, highlights):
    """Format highlights with separators and no metadata"""
    header_lines = [book_name, author] if author else [book_name]
    header = '\n'.join(header_lines) + '\n\n---\n\n'
    return header + '\n\n---\n\n'.join(highlights)


def simplify_file(file_path, output_dir):
    """Write a simplified copy of one book file, returning the book's name

    Returns None when the file isn't a Klippings export.
    """
    book_name, author, highlights = parse_exported_text(read_file_with_encoding(file_path))
    if not book_name:
        return None

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, os.path.basename(file_path))
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(format_highlights(book_name, author, highlights))
    return book_name
