import os

from PIL import Image, ImageFont

from klippings.images import (
    DEFAULT_FONT,
    attribution_text,
    draw_image,
    existing_image_folders,
    export_images,
    fits,
    fullest_page_end,
    images_needed,
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


def test_just_over_one_image_is_shared_evenly():
    font = ImageFont.truetype(FONT, 40)
    # No sentence endings, so only evenness decides where it breaks
    word = "word "
    text = word.strip()
    while fits(wrap_lines(text), font):
        text += " " + word.strip()
    pages = layout_pages(text, font)
    assert len(pages) == 2
    assert abs(len(pages[0]) - len(pages[1])) <= 1
    assert " ".join(" ".join(lines) for lines in pages) == text


def test_breaks_at_a_sentence_end_close_to_even():
    font = ImageFont.truetype(FONT, 40)
    filler = "word " * 90
    text = (filler + "Ends here. " + filler + "word word word").strip()
    pages = layout_pages(text, font)
    assert len(pages) == 2
    assert " ".join(pages[0]).endswith("Ends here.")


def test_breaks_between_words_when_no_sentence_end_is_close():
    font = ImageFont.truetype(FONT, 40)
    text = ("Too early. " + "word " * 200).strip()
    pages = layout_pages(text, font)
    assert not " ".join(pages[0]).endswith("Too early.")
    assert abs(len(pages[0]) - len(pages[1])) <= 1


def test_even_sharing_never_adds_images_or_overflows():
    font = ImageFont.truetype(FONT, 40)
    for length in (1, 10, 18, 25, 40, 77, 130, 200):
        text = " ".join(f"Sentence {i} has a few more words in it." for i in range(length))
        pages = layout_pages(text, font)
        assert len(pages) == images_needed(text, font)
        assert all(fits(lines, font) for lines in pages)
        assert " ".join(" ".join(lines) for lines in pages) == text


def test_several_images_stay_close_in_length():
    font = ImageFont.truetype(FONT, 40)
    text = " ".join(f"Sentence {i} has a few more words in it." for i in range(120))
    sizes = [len(lines) for lines in layout_pages(text, font)]
    assert len(sizes) > 2
    assert max(sizes) - min(sizes) <= 2 * 3


def test_fullest_page_end_cuts_a_word_too_long_for_one_image():
    font = ImageFont.truetype(FONT, 40)
    assert 0 < fullest_page_end("x" * 2500, font) < 2500


def tick_colors(image, total):
    """Read each tick's color from where it should be, centred at the top of the image"""
    x = (image.width - (total * 3 + (total - 1) * 16)) // 2
    return [image.getpixel((x + 19 * tick + 1, 100)) for tick in range(total)]


def test_split_images_show_which_one_they_are_at_the_top_centre():
    font = ImageFont.truetype(FONT, 40)
    current, other = (0x8f, 0x8f, 0x8f), (0xd4, 0xd4, 0xd4)
    for part, expected in ((1, [current, other, other]), (2, [other, current, other]), (3, [other, other, current])):
        image = draw_image(font, font, ["text"], "Book | Author", part, 3)
        assert tick_colors(image, 3) == expected


def test_single_images_have_no_ticks():
    font = ImageFont.truetype(FONT, 40)
    image = draw_image(font, font, ["text"], "Book | Author")
    assert image.crop((0, 0, image.width, 150)).getcolors() == [(image.width * 150, (255, 255, 255))]


def test_ticks_stay_clear_of_a_full_image_of_text():
    font = ImageFont.truetype(FONT, 40)
    lines = wrap_lines(SENTENCE * 40)
    while not fits(lines, font):
        lines.pop()
    plain = draw_image(font, font, lines, "Book | Author")
    assert plain.crop((0, 0, plain.width, 120)).getcolors() == [(plain.width * 120, (255, 255, 255))]


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
