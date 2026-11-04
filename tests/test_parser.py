from klippings.parser import parse_clippings, read_file_with_encoding, split_title_and_author

MODERN = "Your Highlight on page 5 | location 70-71"


def entry(title_line, metadata, body):
    return f"{title_line}\n- {metadata} | Added on Monday, 1 January 2024 10:00:00\n\n{body}\n==========\n"


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


def test_exact_duplicates_are_removed_but_same_text_elsewhere_is_kept():
    content = (
        entry("Book A (Auth A)", MODERN, "hello")
        + entry("Book A (Auth A)", MODERN, "hello")
        + entry("Book A (Auth A)", "Your Highlight on page 9 | location 90", "hello")
        + entry("Book B (Auth B)", MODERN, "hello")
    )
    books, stats = parse_clippings(content)
    assert len(books["Book A"]) == 2
    assert len(books["Book B"]) == 1
    assert stats["duplicate"] == 1


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
