"""Parse My Clippings.txt files into highlights grouped by book."""

from collections import Counter
from datetime import datetime
import codecs
import re

ENTRY_SEPARATOR = re.compile(r'^={10}[ \t]*$', re.MULTILINE)
TITLE_AND_AUTHOR = re.compile(r'^(.*?)\s*\(((?:[^()]|\([^()]*\))*)\)$')
ENTRY_TYPE = re.compile(r'^-\s*(?:Your\s+)?(Highlight|Note|Bookmark|Clip)\b', re.IGNORECASE)
PAGE = re.compile(r'\bpage\s+([^\s|]+)', re.IGNORECASE)
LOCATION = re.compile(r'\b(?:location|loc\.)\s*([^\s|]+)', re.IGNORECASE)
ADDED_ON = re.compile(r'\|\s*Added on\b.*$', re.IGNORECASE)
ADDED_DATE_DAY_FIRST = re.compile(r'\bAdded on\b.*?\b(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})', re.IGNORECASE)
ADDED_DATE_MONTH_FIRST = re.compile(r'\bAdded on\b.*?\b(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})', re.IGNORECASE)
ADDED_TIME = re.compile(r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AP])\.?M\b)?', re.IGNORECASE)
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december')
LEADING_NUMBER = re.compile(r'\D*(\d+)')
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


def parse_added_on(line):
    """Return when a clipping was added, or None if its metadata line has no date we can read"""
    date = ADDED_DATE_DAY_FIRST.search(line) or ADDED_DATE_MONTH_FIRST.search(line)
    if not date or date.group('month').lower() not in MONTHS:
        return None

    time = ADDED_TIME.search(line, date.end())
    hour, minute, second, meridiem = time.groups() if time else (0, 0, 0, None)
    hour = int(hour)
    if meridiem:
        hour = hour % 12 + (12 if meridiem.upper() == 'P' else 0)
    try:
        return datetime(
            int(date.group('year')),
            MONTHS.index(date.group('month').lower()) + 1,
            int(date.group('day')),
            hour,
            int(minute),
            int(second or 0)
        )
    except ValueError:
        return None


def place_in_book(highlight):
    """Return a highlight's position as (location, page), with anything unknown placed last"""
    numbers = []
    for value in (highlight[3], highlight[2]):
        match = LEADING_NUMBER.match(value)
        numbers.append(int(match.group(1)) if match else float('inf'))
    return tuple(numbers)


def in_order_taken(highlights, added_dates):
    """Sort by date, then by place, using place alone unless every date could be read"""
    pairs = list(zip(highlights, added_dates))
    if all(added_dates):
        pairs.sort(key=lambda pair: (pair[1], place_in_book(pair[0])))
    else:
        pairs.sort(key=lambda pair: place_in_book(pair[0]))
    return [highlight for highlight, _ in pairs]


def parse_contents(contents, sort_highlights=False):
    """Organize the highlights of each file's text by book, returning (books, counts of each outcome)

    A highlight identical to one in an earlier file is a copy and is left out, while
    repeats within one file are kept, so a merge holds as many as any one file does.
    """
    books = {}
    added_dates = {}
    stats = Counter()
    seen_in_earlier_files = Counter()

    for content in contents:
        seen_in_this_file = Counter()

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

            # The first two lines hold the book, author, page, location and date exactly as written
            identity = (lines[0].strip(), lines[1].strip(), highlight_text)
            seen_in_this_file[identity] += 1
            if seen_in_this_file[identity] <= seen_in_earlier_files[identity]:
                stats['copy'] += 1
                continue

            book_title, author = split_title_and_author(lines[0].strip())
            books.setdefault(book_title, []).append((highlight_text, author, page_info, location_info))
            added_dates.setdefault(book_title, []).append(parse_added_on(lines[1]))
            stats['highlight'] += 1

        seen_in_earlier_files |= seen_in_this_file

    if sort_highlights:
        books = {title: in_order_taken(highlights, added_dates[title]) for title, highlights in books.items()}

    return books, stats


def parse_clippings(content, sort_highlights=False):
    """Organize one file's highlights by book, returning (books, counts of each outcome)"""
    return parse_contents([content], sort_highlights)


def parse_clipping_files(filenames):
    """Parse several files as one, merging shared books and putting highlights in the order taken"""
    contents = [read_file_with_encoding(filename) for filename in filenames]
    return parse_contents(contents, sort_highlights=len(filenames) > 1)
