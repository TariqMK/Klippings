"""Turn highlights into quote images, one folder per book."""

import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

from klippings.exporter import build_file_stems, short_title

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONT_EXTENSIONS = ('.ttf', '.otf')
DEFAULT_FONT = 'Vollkorn'
FONT_FILE_ENDING = re.compile(r'-(?:Regular|VariableFont.*)$', re.IGNORECASE)

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1350
TEXT_HEIGHT = IMAGE_HEIGHT - 300
FONT_SIZE = 40
WRAP_WIDTH = 43
LINE_SPACING = 15
SENTENCE_TOLERANCE_LINES = 3
ATTRIBUTION_FONT_SIZE = 27
ATTRIBUTION_BOTTOM = 80
WEBP_QUALITY = 85

SENTENCE_END = re.compile(r'[.!?…]["\'”’)\]]*\s+')
IMAGE_FILE = re.compile(r'^Highlight_\d{4}(?:_\d{2})?\.webp$')
MEASURE = ImageDraw.Draw(Image.new('RGB', (1, 1)))


def list_fonts(fonts_dir=FONTS_DIR):
    """Return {display name: path} for the fonts in a folder, with the default first"""
    try:
        file_names = sorted(os.listdir(fonts_dir), key=str.casefold)
    except OSError:
        return {}

    fonts = {
        FONT_FILE_ENDING.sub('', os.path.splitext(file_name)[0]): os.path.join(fonts_dir, file_name)
        for file_name in file_names
        if file_name.lower().endswith(FONT_EXTENSIONS)
    }
    return dict(sorted(fonts.items(), key=lambda font: font[0] != DEFAULT_FONT))


def most_that_fit(count, fit):
    """Find the largest number from 1 to count that fits, by halving the range"""
    low, high = 1, count
    while low < high:
        middle = (low + high + 1) // 2
        if fit(middle):
            low = middle
        else:
            high = middle - 1
    return low


def wrap_lines(text):
    """Wrap text to a set number of characters, keeping its line breaks"""
    lines = []
    for paragraph in text.split('\n'):
        lines.extend(textwrap.wrap(paragraph, width=WRAP_WIDTH) or [''])
    return lines


def text_box(lines, font):
    return MEASURE.multiline_textbbox((0, 0), '\n'.join(lines), font=font, spacing=LINE_SPACING)


def fits(lines, font):
    return text_box(lines, font)[3] <= TEXT_HEIGHT


def word_ends_in(text):
    return [match.end() for match in re.finditer(r'\S+', text)]


def fullest_page_end(text, font):
    """Find where an image would end if it held as much of the text as it can"""
    word_ends = word_ends_in(text)

    def text_up_to_fits(end):
        return fits(wrap_lines(text[:end]), font)

    end = word_ends[most_that_fit(len(word_ends), lambda count: text_up_to_fits(word_ends[count - 1])) - 1]
    if not text_up_to_fits(end):
        # Even the first word is too long for one image, so it has to be cut
        return most_that_fit(end, text_up_to_fits)
    return end


def images_needed(text, font):
    """Count the fewest images that can hold this text"""
    count = 1
    while not fits(wrap_lines(text), font):
        text = text[fullest_page_end(text, font):].strip()
        count += 1
    return count


def even_page_end(text, font, images_left):
    """Find where the next image should end to share the text evenly across those left"""
    target = -(-len(wrap_lines(text)) // images_left)

    def line_count(end):
        return len(wrap_lines(text[:end]))

    def works(end):
        return fits(wrap_lines(text[:end]), font) and images_needed(text[end:].strip(), font) <= images_left - 1

    # A sentence ending close to an even share is the most natural place to stop
    sentence_ends = [match.end() for match in SENTENCE_END.finditer(text)]
    nearby = [end for end in sentence_ends if abs(line_count(end) - target) <= SENTENCE_TOLERANCE_LINES]
    for end in sorted(nearby, key=lambda end: abs(line_count(end) - target)):
        if works(end):
            return end

    word_ends = word_ends_in(text)
    end = word_ends[most_that_fit(len(word_ends), lambda count: line_count(word_ends[count - 1]) <= target) - 1]
    return end if works(end) else fullest_page_end(text, font)


def layout_pages(text, font):
    """Share one highlight's wrapped lines evenly across the fewest images it needs"""
    pages = []
    remaining = text
    for images_left in range(images_needed(text, font), 1, -1):
        end = even_page_end(remaining, font, images_left)
        pages.append(wrap_lines(remaining[:end].strip()))
        remaining = remaining[end:].strip()
    pages.append(wrap_lines(remaining))
    return pages


def attribution_text(book_title, author):
    title = short_title(book_title)
    return f'{title} | {author}' if author else title


def draw_image(font, attribution_font, lines, attribution):
    image = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), color='white')
    draw = ImageDraw.Draw(image)

    left, top, right, bottom = text_box(lines, font)
    position = ((IMAGE_WIDTH - (right - left)) / 2 - left, (IMAGE_HEIGHT - (bottom - top)) / 2 - top)
    draw.multiline_text(position, '\n'.join(lines), fill='black', font=font, align='left', spacing=LINE_SPACING)

    left, top, right, bottom = draw.textbbox((0, 0), attribution, font=attribution_font)
    position = ((IMAGE_WIDTH - (right - left)) / 2 - left, IMAGE_HEIGHT - ATTRIBUTION_BOTTOM - (bottom - top) - top)
    draw.text(position, attribution, fill='black', font=attribution_font)
    return image


def existing_image_folders(books, output_dir, all_titles=None):
    """List the book folders whose images an export would replace"""
    file_stems = build_file_stems(all_titles if all_titles is not None else books)
    folders = (os.path.join(output_dir, file_stems[title]) for title in books)
    return [folder for folder in folders if image_files(folder)]


def image_files(folder):
    """List the images Klippings made in a folder, leaving anything else alone"""
    try:
        return [os.path.join(folder, name) for name in os.listdir(folder) if IMAGE_FILE.match(name)]
    except OSError:
        return []


def export_images(books, output_dir, font_path, all_titles=None, should_cancel=None, on_book=None):
    """Save each book's highlights as images, returning (title, image count, folder) for each"""
    file_stems = build_file_stems(all_titles if all_titles is not None else books)
    font = ImageFont.truetype(font_path, FONT_SIZE)
    attribution_font = ImageFont.truetype(font_path, ATTRIBUTION_FONT_SIZE)

    results = []
    for book_title, highlights in books.items():
        if should_cancel and should_cancel():
            break
        if on_book:
            on_book(short_title(book_title))

        folder = os.path.join(output_dir, file_stems[book_title])
        os.makedirs(folder, exist_ok=True)
        # Old images could outnumber the new ones, so they would otherwise be left behind
        for path in image_files(folder):
            os.remove(path)

        attribution = None
        image_count = 0
        for number, (highlight_text, author, _, _) in enumerate(highlights, start=1):
            if should_cancel and should_cancel():
                break

            attribution = attribution_text(book_title, author)
            text = highlight_text[0].upper() + highlight_text[1:]
            pages = layout_pages(text, font)
            for part, lines in enumerate(pages, start=1):
                ending = f'_{part:02}' if len(pages) > 1 else ''
                image = draw_image(font, attribution_font, lines, attribution)
                image.save(os.path.join(folder, f'Highlight_{number:04}{ending}.webp'), format='WEBP', quality=WEBP_QUALITY)
                image_count += 1

        results.append((short_title(book_title), image_count, folder))

    return results
