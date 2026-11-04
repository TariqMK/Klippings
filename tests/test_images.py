import os

from PIL import Image, ImageFont

from klippings.images import (
    DEFAULT_FONT,
    attribution_text,
    existing_image_folders,
    export_images,
    layout_pages,
    list_fonts,
    wrap_lines,
)

FONT = list_fonts()[DEFAULT_FONT]
SENTENCE = "This sentence is here to fill up the page with text. "


def highlight(text, author="Auth"):
    return (text, author, "page 5", "70-71")


def export(tmp_path, text):
    export_images({"Book": [highlight(text)]}, str(tmp_path), FONT)
    return sorted(os.listdir(tmp_path / "Book"))


def size_of(tmp_path, name):
    with Image.open(tmp_path / "Book" / name) as image:
        return image.size


def test_fonts_list_the_default_first_with_tidy_names(tmp_path):
    for name in ("Alpha-Regular.ttf", "Vollkorn-Regular.ttf", "Beta-VariableFont_wght.ttf", "Gamma-Bold.otf", "notes.txt"):
        (tmp_path / name).write_text("")
    assert list(list_fonts(str(tmp_path))) == ["Vollkorn", "Alpha", "Beta", "Gamma-Bold"]


def test_missing_fonts_folder_lists_nothing(tmp_path):
    assert list_fonts(str(tmp_path / "missing")) == {}


def test_each_book_gets_its_own_folder_of_numbered_images(tmp_path):
    books = {"Book: Sub": [highlight("one"), highlight("two")], "Other": [highlight("three")]}
    results = export_images(books, str(tmp_path), FONT)
    assert [result[:2] for result in results] == [("Book", 2), ("Other", 1)]
    assert sorted(os.listdir(tmp_path / "Book")) == ["Highlight_0001.webp", "Highlight_0002.webp"]
    assert os.listdir(tmp_path / "Other") == ["Highlight_0001.webp"]


def test_short_and_long_quotes_are_the_same_size(tmp_path):
    export(tmp_path, "short")
    assert size_of(tmp_path, "Highlight_0001.webp") == (1080, 1350)
    export(tmp_path, SENTENCE * 12)
    assert size_of(tmp_path, "Highlight_0001.webp") == (1080, 1350)


def test_oversized_text_continues_across_numbered_images(tmp_path):
    names = export(tmp_path, SENTENCE * 100)
    assert len(names) > 1
    assert names[:2] == ["Highlight_0001_01.webp", "Highlight_0001_02.webp"]
    assert all(size_of(tmp_path, name) == (1080, 1350) for name in names)


def test_split_images_keep_every_word_and_end_on_sentences(tmp_path):
    text = " ".join(f"Sentence number {i} is here to fill up the page with text." for i in range(150))
    pages = layout_pages(text, ImageFont.truetype(FONT, 40))
    assert len(pages) > 1
    assert " ".join(" ".join(lines) for lines in pages) == text
    assert all(" ".join(lines).endswith(".") for lines in pages)


def test_lines_wrap_at_43_characters_and_keep_line_breaks():
    lines = wrap_lines(SENTENCE * 5 + "\n\nNew paragraph.")
    assert max(len(line) for line in lines) <= 43
    assert lines[-2:] == ["", "New paragraph."]


def test_one_very_long_word_still_fits(tmp_path):
    assert export(tmp_path, "x" * 2500)


def test_attribution_keeps_punctuation():
    assert attribution_text("Man's Search: For Meaning", "Viktor E. Frankl") == "Man's Search | Viktor E. Frankl"
    assert attribution_text("document.pdf", "") == "document.pdf"


def test_replacing_removes_only_the_images_klippings_made(tmp_path):
    export(tmp_path, SENTENCE * 100)
    assert existing_image_folders({"Book": []}, str(tmp_path)) == [str(tmp_path / "Book")]
    (tmp_path / "Book" / "my notes.txt").write_text("mine")
    (tmp_path / "Book" / "Highlight_0001_edited.webp").write_text("mine")
    names = export(tmp_path, "short")
    assert names == ["Highlight_0001.webp", "Highlight_0001_edited.webp", "my notes.txt"]


def test_folders_without_images_are_not_reported_as_replaced(tmp_path):
    (tmp_path / "Book").mkdir()
    (tmp_path / "Book" / "my notes.txt").write_text("mine")
    assert existing_image_folders({"Book": [], "Other": []}, str(tmp_path)) == []


def test_cancel_stops_before_the_next_image(tmp_path):
    calls = iter([False, False, True])
    books = {"Book": [highlight("one"), highlight("two")], "Other": [highlight("three")]}
    results = export_images(books, str(tmp_path), FONT, should_cancel=lambda: next(calls, True))
    assert results[0][:2] == ("Book", 1)
    assert not (tmp_path / "Other").exists()
