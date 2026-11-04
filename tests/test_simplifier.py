from klippings.exporter import save_highlights_to_files
from klippings.simplifier import simplify_file


def simplify(tmp_path, title, highlights):
    raw = tmp_path / "raw"
    simple = tmp_path / "simple"
    path = save_highlights_to_files({title: highlights}, str(raw))[0][2]
    assert simplify_file(path, str(simple))
    return next(simple.iterdir()).read_text(encoding="utf-8")


def test_modern_format(tmp_path):
    result = simplify(tmp_path, "Book: Sub", [("one", "Auth", "page 5", "70-71"), ("two", "Auth", "page 6", "80")])
    assert result == "Book\nAuth\n\n---\n\n1. one\n\n---\n\n2. two"


def test_metadata_is_removed_for_every_format(tmp_path):
    highlights = [("one", "Auth", "", "70-71"), ("two", "Auth", "page 5", ""), ("three", "Auth", "", "")]
    result = simplify(tmp_path, "Book", highlights)
    assert result == "Book\nAuth\n\n---\n\n1. one\n\n---\n\n2. two\n\n---\n\n3. three"


def test_book_without_author(tmp_path):
    result = simplify(tmp_path, "document.pdf", [("one", "", "page 5", "70")])
    assert result == "document.pdf\n\n---\n\n1. one"


def test_highlights_with_blank_lines_and_angle_brackets(tmp_path):
    highlights = [("para one\n\npara two", "Auth", "page 1", "1"), ("a <b>(c) d", "Auth", "page 2", "2")]
    result = simplify(tmp_path, "Book", highlights)
    assert result == "Book\nAuth\n\n---\n\n1. para one\n\npara two\n\n---\n\n2. a <b>(c) d"


def test_exports_from_older_versions(tmp_path):
    old = tmp_path / "old.txt"
    old.write_text(
        "1. one\n\t<Book>(Auth) Your Highlight on  | location location 70-71\n\n"
        "2. two\n\t<Book>(Auth) Your Highlight on Highlight on Page 5 | location Loc. 70-71\n\n",
        encoding="utf-8",
    )
    simplify_file(str(old), str(tmp_path / "simple"))
    assert (tmp_path / "simple" / "old.txt").read_text(encoding="utf-8") == "Book\nAuth\n\n---\n\n1. one\n\n---\n\n2. two"


def test_other_text_files_are_left_alone(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("just some notes", encoding="utf-8")
    assert simplify_file(str(other), str(tmp_path / "simple")) is None
    assert not (tmp_path / "simple").exists()
