from klippings.exporter import (
    build_file_stems,
    existing_files,
    export_books,
    format_metadata,
    safe_file_stem,
)

HIGHLIGHT = [("hello", "Auth", "page 5", "70-71")]


def names(path):
    return sorted(p.name for p in path.iterdir())


def test_files_go_directly_in_the_chosen_folder(tmp_path):
    export_books({"Book": HIGHLIGHT}, str(tmp_path))
    assert names(tmp_path) == ["Book (with metadata).txt", "Book.txt"]
    assert all(p.is_file() for p in tmp_path.iterdir())


def test_each_format_can_be_exported_alone(tmp_path):
    only_text = tmp_path / "text"
    only_metadata = tmp_path / "metadata"
    export_books({"Book": HIGHLIGHT}, str(only_text), with_metadata=False)
    export_books({"Book": HIGHLIGHT}, str(only_metadata), text_only=False)
    assert names(only_text) == ["Book.txt"]
    assert names(only_metadata) == ["Book (with metadata).txt"]


def test_metadata_format(tmp_path):
    results = export_books({"Book: Sub": HIGHLIGHT}, str(tmp_path), text_only=False)
    title, count, paths = results[0]
    assert (title, count) == ("Book", 1)
    with open(paths[0], encoding="utf-8") as file:
        assert file.read() == "1. hello\n\t<Book: Sub>(Auth) Your Highlight on page 5 | location 70-71\n\n"


def test_text_only_format(tmp_path):
    highlights = [("one", "Auth", "page 5", "70-71"), ("para one\n\npara two", "Auth", "", ""), ("a <b>(c) d", "Auth", "", "9")]
    export_books({"Book: Sub": highlights}, str(tmp_path), with_metadata=False)
    assert (tmp_path / "Book.txt").read_text(encoding="utf-8") == (
        "Book\nAuth\n\n---\n\n1. one\n\n---\n\n2. para one\n\npara two\n\n---\n\n3. a <b>(c) d"
    )


def test_text_only_without_author(tmp_path):
    export_books({"document.pdf": [("one", "", "page 5", "70")]}, str(tmp_path), with_metadata=False)
    assert (tmp_path / "document.pdf.txt").read_text(encoding="utf-8") == "document.pdf\n\n---\n\n1. one"


def test_titles_sharing_a_short_title_get_separate_files():
    assert build_file_stems(["Same: Part One", "Same: Part Two", "Other: Part"]) == {
        "Same: Part One": "Same Part One",
        "Same: Part Two": "Same Part Two",
        "Other: Part": "Other",
    }


def test_file_names_do_not_depend_on_which_book_is_saved(tmp_path):
    titles = ["Same: Part One", "Same: Part Two"]
    export_books({titles[0]: HIGHLIGHT}, str(tmp_path), with_metadata=False, all_titles=titles)
    export_books({titles[1]: HIGHLIGHT}, str(tmp_path), with_metadata=False, all_titles=titles)
    assert names(tmp_path) == ["Same Part One.txt", "Same Part Two.txt"]


def test_titles_differing_only_by_case_get_separate_files():
    stems = build_file_stems(["book", "BOOK"])
    assert len({stem.casefold() for stem in stems.values()}) == 2


def test_safe_file_stem():
    assert safe_file_stem('A/B\\C<D>E"F|G?H*') == "ABCDEFGH"
    assert safe_file_stem("Trailing dots...") == "Trailing dots"
    assert safe_file_stem("CON") == "CON_"
    assert safe_file_stem("???") == "Untitled"
    assert len(safe_file_stem("x" * 500)) == 120


def test_title_starting_with_colon_keeps_its_name():
    assert build_file_stems([": Subtitle"]) == {": Subtitle": "Subtitle"}


def test_format_metadata():
    assert format_metadata("page 5", "70-71") == "Your Highlight on page 5 | location 70-71"
    assert format_metadata("page 5", "") == "Your Highlight on page 5"
    assert format_metadata("", "70-71") == "Your Highlight at location 70-71"
    assert format_metadata("", "") == "Your Highlight"


def test_existing_files_only_lists_files_the_export_would_replace(tmp_path):
    books = {"Book": HIGHLIGHT, "Other": HIGHLIGHT}
    (tmp_path / "Book.txt").write_text("mine", encoding="utf-8")
    (tmp_path / "Book (with metadata).txt").write_text("mine", encoding="utf-8")
    (tmp_path / "Unrelated.txt").write_text("mine", encoding="utf-8")
    assert existing_files(books, str(tmp_path), with_metadata=False) == [str(tmp_path / "Book.txt")]
    assert len(existing_files(books, str(tmp_path))) == 2
    assert existing_files({"Other": HIGHLIGHT}, str(tmp_path)) == []


def test_cancel_stops_before_the_next_book(tmp_path):
    books = {"A": [("x", "", "", "")], "B": [("y", "", "", "")]}
    calls = iter([False, True])
    results = export_books(books, str(tmp_path), with_metadata=False, should_cancel=lambda: next(calls))
    assert [r[0] for r in results] == ["A"]
    assert names(tmp_path) == ["A.txt"]
