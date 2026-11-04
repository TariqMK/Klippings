from klippings.exporter import build_file_names, format_metadata, safe_file_stem, save_highlights_to_files


def test_titles_sharing_a_short_title_get_separate_files():
    names = build_file_names(["Same: Part One", "Same: Part Two", "Other: Part"])
    assert names == {
        "Same: Part One": "Same Part One.txt",
        "Same: Part Two": "Same Part Two.txt",
        "Other: Part": "Other.txt",
    }


def test_file_names_do_not_depend_on_which_book_is_saved(tmp_path):
    titles = ["Same: Part One", "Same: Part Two"]
    highlight = [("text", "X", "page 1", "2")]
    first = save_highlights_to_files({titles[0]: highlight}, str(tmp_path), titles)
    second = save_highlights_to_files({titles[1]: highlight}, str(tmp_path), titles)
    assert first[0][2] != second[0][2]
    assert len(list(tmp_path.iterdir())) == 2


def test_titles_differing_only_by_case_get_separate_files():
    names = build_file_names(["book", "BOOK"])
    assert len({name.casefold() for name in names.values()}) == 2


def test_safe_file_stem():
    assert safe_file_stem('A/B\\C<D>E"F|G?H*') == "ABCDEFGH"
    assert safe_file_stem("Trailing dots...") == "Trailing dots"
    assert safe_file_stem("CON") == "CON_"
    assert safe_file_stem("???") == "Untitled"
    assert len(safe_file_stem("x" * 500)) == 120


def test_title_starting_with_colon_keeps_its_name():
    assert build_file_names([": Subtitle"]) == {": Subtitle": "Subtitle.txt"}


def test_format_metadata():
    assert format_metadata("page 5", "70-71") == "Your Highlight on page 5 | location 70-71"
    assert format_metadata("page 5", "") == "Your Highlight on page 5"
    assert format_metadata("", "70-71") == "Your Highlight at location 70-71"
    assert format_metadata("", "") == "Your Highlight"


def test_saved_file_format(tmp_path):
    results = save_highlights_to_files({"Book: Sub": [("hello", "Auth", "page 5", "70-71")]}, str(tmp_path))
    title, count, path = results[0]
    assert (title, count) == ("Book", 1)
    with open(path, encoding="utf-8") as file:
        assert file.read() == "1. hello\n\t<Book: Sub>(Auth) Your Highlight on page 5 | location 70-71\n\n"


def test_cancel_stops_before_the_next_book(tmp_path):
    books = {"A": [("x", "", "", "")], "B": [("y", "", "", "")]}
    calls = iter([False, True])
    results = save_highlights_to_files(books, str(tmp_path), should_cancel=lambda: next(calls))
    assert [r[0] for r in results] == ["A"]
    assert [p.name for p in tmp_path.iterdir()] == ["A.txt"]
