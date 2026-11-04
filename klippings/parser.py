"""Parse My Clippings.txt into highlights grouped by book."""

from collections import Counter
import codecs
import re

ENTRY_SEPARATOR = re.compile(r'^={10}[ \t]*$', re.MULTILINE)
TITLE_AND_AUTHOR = re.compile(r'^(.*?)\s*\(((?:[^()]|\([^()]*\))*)\)$')
ENTRY_TYPE = re.compile(r'^-\s*(?:Your\s+)?(Highlight|Note|Bookmark|Clip)\b', re.IGNORECASE)
PAGE = re.compile(r'\bpage\s+([^\s|]+)', re.IGNORECASE)
LOCATION = re.compile(r'\b(?:location|loc\.)\s*([^\s|]+)', re.IGNORECASE)
ADDED_ON = re.compile(r'\|\s*Added on\b.*$', re.IGNORECASE)
CLIPPING_LIMIT = '<You have reached the clipping limit'


def read_file_with_encoding(filename):
    """Read a text file in whichever encoding it was saved with"""
    with open(filename, 'rb') as file:
        data = file.read()

    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode('utf-16')
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = data.decode('cp1252')
            except UnicodeDecodeError:
                text = data.decode('iso-8859-1')

    return text.replace('\r\n', '\n').replace('\r', '\n')


def split_title_and_author(line):
    """Split 'Title (Author)' using the last bracketed group as the author"""
    match = TITLE_AND_AUTHOR.match(line)
    if match and match.group(1):
        return match.group(1), match.group(2).strip()
    return line, ''


def parse_metadata(line):
    """Return (entry type, page, location) from a clipping's metadata line"""
    entry_type = ENTRY_TYPE.match(line)
    details = ADDED_ON.sub('', line)
    page = PAGE.search(details)
    location = LOCATION.search(details)
    return (
        entry_type.group(1).lower() if entry_type else None,
        f"page {page.group(1)}" if page else '',
        location.group(1) if location else ''
    )


def parse_clippings(content):
    """Organize highlights by book, returning (books, counts of each outcome)"""
    books = {}
    seen = set()
    stats = Counter()

    for entry in ENTRY_SEPARATOR.split(content):
        lines = entry.strip().lstrip('﻿').strip().split('\n')
        if lines == ['']:
            continue

        entry_type = None
        if len(lines) >= 2:
            entry_type, page_info, location_info = parse_metadata(lines[1].strip())

        if entry_type is None:
            stats['unrecognised'] += 1
            continue
        if entry_type != 'highlight':
            stats[entry_type] += 1
            continue

        highlight_text = '\n'.join(lines[2:]).strip()
        if not highlight_text:
            stats['empty'] += 1
            continue
        if highlight_text.startswith(CLIPPING_LIMIT):
            stats['clipping_limit'] += 1
            continue

        book_title, author = split_title_and_author(lines[0].strip())
        key = (book_title, highlight_text, page_info, location_info)
        if key in seen:
            stats['duplicate'] += 1
            continue
        seen.add(key)

        books.setdefault(book_title, []).append((highlight_text, author, page_info, location_info))
        stats['highlight'] += 1

    return books, stats
