from datetime import datetime

from klippings.parser import parse_added_on, parse_clipping_files, parse_clippings, read_file_with_encoding, split_title_and_author

MODERN = "Your Highlight on page 5 | location 70-71"


def entry(title_line, metadata, body):
    return f"{title_line}\n- {metadata} | Added on Monday, 1 January 2024 10:00:00\n\n{body}\n==========\n"


def dated(body, location, added_on):
    return f"Book A (Auth A)\n- Your Highlight on page 5 | location {location} | Added on {added_on}\n\n{body}\n==========\n"


def open_as_files(tmp_path, *contents):
    paths = []
    for number, content in enumerate(contents):
        path = tmp_path / f"{number}.txt"
        path.write_text(content, encoding="utf-8")
        paths.append(str(path))
    return parse_clipping_files(paths)[0]


def bodies(books):
    return [h[0] for h in books["Book A"]]


def test_reads_the_added_on_date_formats():
    assert parse_added_on("- Your Highlight on page 5 | Added on Monday, 1 January 2024 10:00:00") == datetime(2024, 1, 1, 10, 0, 0)
    assert parse_added_on("- Your Highlight on page 5 | Added on Sunday, March 5, 2017 3:13:32 PM") == datetime(2017, 3, 5, 15, 13, 32)
    assert parse_added_on("- Highlight Loc. 70 | Added on Friday, April 13, 2012, 12:03 AM") == datetime(2012, 4, 13, 0, 3)
    assert parse_added_on("- Your Highlight | Added on Friday, April 13, 2012, 12:03 PM") == datetime(2012, 4, 13, 12, 3)


def test_unreadable_dates_give_none():
    assert parse_added_on("- Your Highlight on page 5") is None
    assert parse_added_on("- Your Highlight | Added on Lundi 1 Janvier 2024 10:00:00") is None
    assert parse_added_on("- Your Highlight | Added on Monday, 31 February 2024 10:00:00") is None
    assert parse_added_on("- Your Highlight | Added on Monday, 1 January 2024 99:00:00") is None


def test_several_files_are_sorted_by_date_whichever_opens_first(tmp_path):
    newer = dated("mar", 300, "Friday, 1 March 2024 10:00:00") + dated("apr", 100, "Monday, 1 April 2024 10:00:00")
    older = dated("jan", 400, "Monday, 1 January 2024 10:00:00") + dated("feb", 200, "Thursday, 1 February 2024 10:00:00")
    assert bodies(open_as_files(tmp_path, newer, older)) == ["jan", "feb", "mar", "apr"]
    assert bodies(open_as_files(tmp_path, older, newer)) == ["jan", "feb", "mar", "apr"]


def test_location_breaks_ties_between_highlights_taken_at_the_same_time(tmp_path):
    same_time = "Monday, 1 January 2024 10:00:00"
    books = open_as_files(tmp_path, dated("later", "90-91", same_time), dated("earlier", "9-10", same_time))
    assert bodies(books) == ["earlier", "later"]


def test_several_files_use_location_when_any_date_cannot_be_read(tmp_path):
    readable = dated("third", 30, "Monday, 1 January 2024 10:00:00") + dated("first", 10, "Tuesday, 2 January 2024 10:00:00")
    unreadable = dated("second", 20, "Lundi 1 Janvier 2024 10:00:00")
    assert bodies(open_as_files(tmp_path, readable, unreadable)) == ["first", "second", "third"]


def test_a_single_file_keeps_its_own_order(tmp_path):
    content = dated("newer", 10, "Tuesday, 2 January 2024 10:00:00") + dated("older", 20, "Monday, 1 January 2024 10:00:00")
    assert bodies(open_as_files(tmp_path, content)) == ["newer", "older"]


def test_several_files_merge_books_and_keep_repeated_highlights(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text(entry("Book A (Auth A)", MODERN, "shared") + entry("Book A (Auth A)", MODERN, "only first"), encoding="utf-8")
    second.write_text(entry("Book A (Auth A)", MODERN, "shared") + entry("Book B (Auth B)", MODERN, "only second"), encoding="utf-8")
    books, stats = parse_clipping_files([str(first), str(second)])
    assert sorted(h[0] for h in books["Book A"]) == ["only first", "shared", "shared"]
    assert [h[0] for h in books["Book B"]] == ["only second"]
    assert stats["highlight"] == 4


def test_several_files_stay_separate_without_a_final_separator_or_shared_encoding(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_bytes(entry("Book A (Auth A)", MODERN, "caf\u00e9").removesuffix("==========\n").encode("cp1252"))
    second.write_bytes(b"\xef\xbb\xbf" + entry("Book B (Auth B)", MODERN, "two").encode("utf-8"))
    books, _ = parse_clipping_files([str(first), str(second)])
    assert books == {
        "Book A": [("caf\u00e9", "Auth A", "page 5", "70-71")],
        "Book B": [("two", "Auth B", "page 5", "70-71")],
    }


def test_modern_highlight():
    books, stats = parse_clippings(entry("Book A (Auth A)", MODERN, "hello"))
    assert books == {"Book A": [("hello", "Auth A", "page 5", "70-71")]}
    assert stats["highlight"] == 1


def test_highlight_mentioning_a_bookmark_is_kept():
    content = entry("Book A (Auth A)", MODERN, "see Your Bookmark here") + entry("Book A (Auth A)", "Your Highlight on page 6 | location 80", "next")
    books, _ = parse_clippings(content)
    assert [h[0] for h in books["Book A"]] == ["see Your Bookmark here", "next"]


def test_bookmarks_and_notes_are_counted_and_do_not_leak():
    content = (
        entry("Book A (Auth A)", "Your Bookmark on page 5 | location 70", "")
        + entry("Book A (Auth A)", "Your Note on page 5 | location 71", "my note")
        + entry("Book A (Auth A)", MODERN, "hello")
    )
    books, stats = parse_clippings(content)
    assert books == {"Book A": [("hello", "Auth A", "page 5", "70-71")]}
    assert (stats["bookmark"], stats["note"], stats["highlight"]) == (1, 1, 1)


def test_older_metadata_formats():
    cases = {
        "Your Highlight at location 70-71": ("", "70-71"),
        "Your Highlight on Location 70-71": ("", "70-71"),
        "Your Highlight Location 70-71": ("", "70-71"),
        "Highlight on Page 5 | Loc. 70-71": ("page 5", "70-71"),
        "Highlight Loc. 70-71": ("", "70-71"),
        "Your Highlight on page 5": ("page 5", ""),
        "Your Highlight on page ix | location 7": ("page ix", "7"),
    }
    for metadata, (page, location) in cases.items():
        books, _ = parse_clippings(entry("Book A (Auth A)", metadata, "hello"))
        assert books["Book A"] == [("hello", "Auth A", page, location)], metadata


def test_title_and_author_splitting():
    assert split_title_and_author("Book (Vol 1) (Auth A)") == ("Book (Vol 1)", "Auth A")
    assert split_title_and_author("Book (Name (Editor))") == ("Book", "Name (Editor)")
    assert split_title_and_author("document.pdf") == ("document.pdf", "")
    assert split_title_and_author("(Only Brackets)") == ("(Only Brackets)", "")


def test_entry_without_author_stays_separate():
    content = entry("document.pdf", MODERN, "first") + entry("Book A (Auth A)", MODERN, "second")
    books, _ = parse_clippings(content)
    assert books["document.pdf"] == [("first", "", "page 5", "70-71")]
    assert books["Book A"] == [("second", "Auth A", "page 5", "70-71")]


def test_exact_duplicates_are_kept():
    content = (
        entry("Book A (Auth A)", MODERN, "hello")
        + entry("Book A (Auth A)", MODERN, "hello")
        + entry("Book A (Auth A)", "Your Highlight on page 9 | location 90", "hello")
        + entry("Book B (Auth B)", MODERN, "hello")
    )
    books, stats = parse_clippings(content)
    assert len(books["Book A"]) == 3
    assert len(books["Book B"]) == 1
    assert stats["highlight"] == 4


def test_empty_and_clipping_limit_entries_are_skipped():
    content = (
        entry("Book A (Auth A)", MODERN, "")
        + entry("Book A (Auth A)", MODERN, "<You have reached the clipping limit for this item>")
    )
    books, stats = parse_clippings(content)
    assert books == {}
    assert (stats["empty"], stats["clipping_limit"]) == (1, 1)


def test_unrecognised_entries_are_counted():
    books, stats = parse_clippings("not a clipping\n==========\n" + entry("Book A (Auth A)", "Votre surlignement", "hello"))
    assert books == {}
    assert stats["unrecognised"] == 2


def test_byte_order_marks_and_multi_line_highlights():
    content = "﻿" + entry("Book A (Auth A)", MODERN, "one\n\ntwo") + "﻿" + entry("Book A (Auth A)", "Your Highlight on page 6", "three")
    books, _ = parse_clippings(content)
    assert list(books) == ["Book A"]
    assert [h[0] for h in books["Book A"]] == ["one\n\ntwo", "three"]


def test_read_file_with_encoding(tmp_path):
    text = "Café – ‘quoted’\n"
    cases = {
        "utf-8": text.encode("utf-8"),
        "utf-8-bom": b"\xef\xbb\xbf" + text.encode("utf-8"),
        "utf-16": text.encode("utf-16"),
        "cp1252": text.encode("cp1252"),
        "crlf": text.replace("\n", "\r\n").encode("utf-8"),
    }
    for name, data in cases.items():
        path = tmp_path / f"{name}.txt"
        path.write_bytes(data)
        assert read_file_with_encoding(str(path)) == text, name
