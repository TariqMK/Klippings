"""Klippings desktop GUI."""

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import os
import queue
import subprocess
import sys
import threading
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None
    DND_FILES = None
import json

from klippings._version import __version__
from klippings.exporter import RAW_DIR_NAME, save_highlights_to_files
from klippings.parser import parse_clippings, read_file_with_encoding
from klippings.simplifier import SIMPLE_DIR_NAME, simplify_file

NO_FILE_SELECTED = ""
UI_POLL_INTERVAL_MS = 50
WORKER_CLOSE_TIMEOUT_SECONDS = 5
SKIPPED_ENTRY_LABELS = {
    'duplicate': "exact duplicates",
    'note': "notes",
    'bookmark': "bookmarks",
    'clip': "article clips",
    'empty': "empty highlights",
    'clipping_limit': "clipping limit messages",
    'unrecognised': "unrecognised entries"
}

# Colors as (light, dark). Surfaces stay quiet, and the logo's ochre is the only accent.
COLOR_PAGE = ("#f7f4ee", "#161513")
COLOR_SIDEBAR = ("#efebe3", "#121110")
COLOR_RAISED = ("#e4dfd4", "#262421")
COLOR_HAIRLINE = ("#d9d3c7", "#2c2a26")
COLOR_CONTROL_BORDER = ("#8a8275", "#7d776d")
COLOR_TEXT = ("#1f1b16", "#efe9de")
COLOR_TEXT_SECONDARY = ("#5e554a", "#aaa398")
COLOR_TEXT_MUTED = ("#686054", "#918b80")
COLOR_ACCENT = ("#d1a040", "#d1a040")
COLOR_ACCENT_HOVER = ("#c09136", "#deb057")
COLOR_ON_ACCENT = ("#1f1b16", "#1f1b16")
COLOR_MARKER = ("#f6e4ab", "#4a3a16")
COLOR_BAR_EXCLUDED = ("#c9c2b5", "#3a3733")

UI_FONT_FAMILIES = {"win32": "Segoe UI", "darwin": "SF Pro Text"}
UI_FONT = UI_FONT_FAMILIES.get(sys.platform, "Roboto")
READING_FONT = "Georgia" if sys.platform in UI_FONT_FAMILIES else "DejaVu Serif"
MONO_FONTS = {"win32": "Consolas", "darwin": "Menlo"}
MONO_FONT = MONO_FONTS.get(sys.platform, "DejaVu Sans Mono")
SHORTCUT_MODIFIER = "Command" if sys.platform == "darwin" else "Control"

SIDEBAR_WIDTH = 320
BOOK_BAR_MAX_WIDTH = 216
BOOK_TITLE_MAX_WIDTH = 248
READING_MAX_LINE_WIDTH = 680
READING_MARGIN = 32


def asset_path(file_name):
    """Locate a bundled asset, both from source and in a PyInstaller build"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(getattr(sys, "_MEIPASS", project_root), "assets", file_name)


def ui_font(size=13, weight="normal"):
    return ctk.CTkFont(family=UI_FONT, size=size, weight=weight)


def format_count(count, noun):
    """Format a count with its noun, like '1,424 highlights'"""
    return f"{count:,} {noun}{'' if count == 1 else 's'}"


def shorten_path(path, max_length=32):
    """Shorten a folder path from the middle, keeping the end that identifies it"""
    home = os.path.expanduser("~")
    if path == home or path.startswith(home + os.sep):
        path = "~" + path[len(home):]
    if len(path) <= max_length:
        return path
    keep = (max_length - 1) // 2
    return f"{path[:keep]}…{path[-keep:]}"


def shorten_to_width(text, font, max_width):
    """Shorten text from the end until it fits the given width"""
    if font.measure(text) <= max_width:
        return text
    while text and font.measure(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def format_place(page_info, location):
    """Describe where a highlight is, like 'Page 5 · Location 70-71'"""
    start, _, end = location.partition("-")
    location = start if start == end else location
    parts = [page_info.capitalize(), f"Location {location}" if location else ""]
    return " · ".join(part for part in parts if part)


def open_folder(path):
    """Show a folder in the system's file manager"""
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


class BookRow(ctk.CTkFrame):
    """One book in the list: a checkbox, its title, and a marker stroke sized by its highlights"""

    def __init__(self, master, title, count, max_count, variable, on_select):
        super().__init__(master, height=56, corner_radius=8, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.variable = variable
        self.selected = False

        self.checkbox = ctk.CTkCheckBox(
            self,
            text="",
            variable=variable,
            width=24,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            border_width=1,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            border_color=COLOR_CONTROL_BORDER,
            checkmark_color=COLOR_ON_ACCENT
        )
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=(12, 4), pady=8)

        title_font = ui_font(13)
        self.title_label = ctk.CTkLabel(
            self,
            text=shorten_to_width(title, title_font, BOOK_TITLE_MAX_WIDTH),
            font=title_font,
            text_color=COLOR_TEXT,
            height=20,
            anchor="w"
        )
        self.title_label.grid(row=0, column=1, columnspan=2, padx=(0, 12), pady=(8, 0), sticky="ew")

        bar_width = max(8, round(BOOK_BAR_MAX_WIDTH * count / max_count))
        self.bar = ctk.CTkFrame(self, width=bar_width, height=4, corner_radius=2, fg_color=COLOR_ACCENT)
        self.bar.grid(row=1, column=1, padx=(0, 8), pady=(0, 8), sticky="w")

        self.count_label = ctk.CTkLabel(
            self,
            text=f"{count:,}",
            font=ui_font(12),
            text_color=COLOR_TEXT_MUTED,
            height=16,
            anchor="e"
        )
        self.count_label.grid(row=1, column=2, padx=(0, 12), pady=(0, 8), sticky="e")

        for widget in (self, self.title_label, self.count_label, self.bar):
            widget.bind("<Button-1>", lambda event: on_select())
            widget.bind("<Enter>", lambda event: self.show_hover(True))
            widget.bind("<Leave>", lambda event: self.show_hover(False))

        variable.trace_add("write", lambda *args: self.refresh_bar())
        self.refresh_bar()

    def refresh_bar(self):
        self.bar.configure(fg_color=COLOR_ACCENT if self.variable.get() else COLOR_BAR_EXCLUDED)

    def set_selected(self, selected):
        self.selected = selected
        self.configure(fg_color=COLOR_RAISED if selected else "transparent")

    def show_hover(self, hovering):
        if not self.selected:
            self.configure(fg_color=COLOR_HAIRLINE if hovering else "transparent")


class KindleHighlightsGUI:
    def __init__(self):
        # Follow the system's light or dark appearance
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Create main window with drag-drop support if available
        if TkinterDnD:
            # Create TkinterDnD root first
            root = TkinterDnD.Tk()
            root.withdraw()  # Hide the Tk window

            # Create CTk window as Toplevel
            self.root = ctk.CTkToplevel(root)
            self._tk_root = root
        else:
            self.root = ctk.CTk()
            self._tk_root = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.title("Klippings")
        self.root.geometry("1040x680")
        self.root.minsize(760, 520)
        self.root.configure(fg_color=COLOR_PAGE)
        self.set_window_icon()

        # Load saved preferences
        self.config_file = os.path.join(os.path.expanduser("~"), ".kindle_highlights_config.json")
        self.load_preferences()

        # Processing control
        self.is_processing = False
        self.cancel_requested = False
        self.closing = False
        self.worker = None
        self.ui_queue = queue.Queue()
        self.last_output_dir_used = None

        # Books
        self.book_vars = {}
        self.book_data = {}
        self.book_rows = {}
        self.selected_title = None
        self.appearance_mode = ctk.get_appearance_mode()

        self.file_path_var = tk.StringVar(value=NO_FILE_SELECTED)
        self.output_path_var = tk.StringVar(value=self.last_output_dir)
        self.script1_var = tk.BooleanVar(value=True)
        self.script2_var = tk.BooleanVar(value=True)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        self.build_header()
        self.build_hairline(row=1)
        self.build_empty_state()
        self.build_book_view()
        self.build_hairline(row=3)
        self.build_export_bar()
        self.build_status_bar()
        self.build_details()
        self.bind_shortcuts()

        if TkinterDnD and DND_FILES:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.drop_file)
            self.root.dnd_bind('<<DropEnter>>', lambda event: self.show_drop_hover(True))
            self.root.dnd_bind('<<DropLeave>>', lambda event: self.show_drop_hover(False))
        else:
            self.drop_title_prefix.configure(text="Choose ")
            self.drop_title_suffix.configure(text=" to begin")
            self.log("Drag and drop isn't available, as tkinterdnd2 isn't installed")

        self.update_export_state()
        self.poll_ui_queue()

    def build_hairline(self, row):
        line = ctk.CTkFrame(self.root, height=1, corner_radius=0, fg_color=COLOR_HAIRLINE)
        line.grid(row=row, column=0, sticky="ew")

    def build_header(self):
        header = ctk.CTkFrame(self.root, height=56, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(2, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="Klippings",
            font=ctk.CTkFont(family=READING_FONT, size=20),
            text_color=COLOR_TEXT
        )
        self.title_label.grid(row=0, column=0, padx=(24, 8), pady=12)

        self.version_label = ctk.CTkLabel(
            header,
            text=f"v{__version__}",
            font=ui_font(12),
            text_color=COLOR_TEXT_MUTED
        )
        self.version_label.grid(row=0, column=1, pady=(6, 12))

        self.file_label = ctk.CTkLabel(header, text="", font=ui_font(13), text_color=COLOR_TEXT_SECONDARY)
        self.file_label.grid(row=0, column=3, padx=(8, 12))

        self.change_file_button = self.quiet_button(header, "Choose Another File", self.browse_file)
        self.change_file_button.grid(row=0, column=4, padx=(0, 24))
        self.change_file_button.grid_remove()

    def quiet_button(self, master, text, command, **kwargs):
        return ctk.CTkButton(
            master,
            text=text,
            command=command,
            font=ui_font(13),
            height=28,
            width=0,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLOR_RAISED,
            text_color=COLOR_TEXT_SECONDARY,
            **kwargs
        )

    def build_empty_state(self):
        self.empty_state = ctk.CTkFrame(self.root, corner_radius=12, fg_color="transparent", border_width=1, border_color=COLOR_PAGE)
        self.empty_state.grid(row=2, column=0, padx=24, pady=24, sticky="nsew")
        self.empty_state.grid_columnconfigure(0, weight=1)
        self.empty_state.grid_rowconfigure((0, 2), weight=1)

        content = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        content.grid(row=1, column=0)

        title = ctk.CTkFrame(content, fg_color="transparent")
        title.grid(row=0, column=0)
        title_font = ctk.CTkFont(family=READING_FONT, size=28)
        self.drop_title_prefix = ctk.CTkLabel(title, text="Drop ", font=title_font, text_color=COLOR_TEXT)
        self.drop_title_prefix.grid(row=0, column=0)
        marked = ctk.CTkLabel(title, text=" My Clippings.txt ", font=title_font, text_color=COLOR_TEXT, fg_color=COLOR_MARKER, corner_radius=2)
        marked.grid(row=0, column=1)
        self.drop_title_suffix = ctk.CTkLabel(title, text=" here", font=title_font, text_color=COLOR_TEXT)
        self.drop_title_suffix.grid(row=0, column=2)

        hint = ctk.CTkLabel(
            content,
            text="You'll find it in the documents folder on your Kindle",
            font=ui_font(14),
            text_color=COLOR_TEXT_SECONDARY
        )
        hint.grid(row=1, column=0, pady=(12, 24))

        self.browse_button = ctk.CTkButton(
            content,
            text="Choose File",
            command=self.browse_file,
            font=ui_font(13),
            height=36,
            width=120,
            corner_radius=8,
            fg_color=COLOR_RAISED,
            hover_color=COLOR_HAIRLINE,
            text_color=COLOR_TEXT
        )
        self.browse_button.grid(row=2, column=0)

    def build_book_view(self):
        self.book_selection_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.book_selection_frame.grid(row=2, column=0, sticky="nsew")
        self.book_selection_frame.grid_columnconfigure(2, weight=1)
        self.book_selection_frame.grid_rowconfigure(0, weight=1)
        self.book_selection_frame.grid_remove()

        sidebar = ctk.CTkFrame(self.book_selection_frame, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=COLOR_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(1, weight=1)

        self.book_summary_label = ctk.CTkLabel(sidebar, text="", font=ui_font(12), text_color=COLOR_TEXT_MUTED, anchor="w")
        self.book_summary_label.grid(row=0, column=0, padx=(20, 8), pady=(12, 4), sticky="w")

        self.toggle_all_button = self.quiet_button(sidebar, "Select None", self.toggle_all_books)
        self.toggle_all_button.grid(row=0, column=1, padx=(0, 12), pady=(12, 4))

        self.books_scroll_frame = ctk.CTkScrollableFrame(
            sidebar,
            corner_radius=0,
            fg_color="transparent",
            scrollbar_button_color=COLOR_HAIRLINE,
            scrollbar_button_hover_color=COLOR_CONTROL_BORDER
        )
        self.books_scroll_frame.grid(row=1, column=0, columnspan=2, padx=(4, 0), pady=(0, 8), sticky="nsew")
        self.books_scroll_frame.grid_columnconfigure(0, weight=1)
        self.books_scroll_frame.bind("<Configure>", lambda event: self.refresh_book_scrollbar())

        divider = ctk.CTkFrame(self.book_selection_frame, width=1, corner_radius=0, fg_color=COLOR_HAIRLINE)
        divider.grid(row=0, column=1, sticky="ns")

        self.reading_view = ctk.CTkTextbox(
            self.book_selection_frame,
            corner_radius=0,
            border_spacing=0,
            wrap="word",
            fg_color="transparent",
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(family=READING_FONT, size=16),
            scrollbar_button_color=COLOR_HAIRLINE,
            scrollbar_button_hover_color=COLOR_CONTROL_BORDER,
            activate_scrollbars=True
        )
        self.reading_view.grid(row=0, column=2, sticky="nsew")
        self.reading_view.configure(state="disabled")
        # Margins inside the text, so highlights scroll right up to the window's edges
        self.reading_view._textbox.configure(padx=round(self.reading_view._apply_widget_scaling(READING_MARGIN)), pady=0)
        self.reading_view.bind("<Configure>", lambda event: self.limit_reading_line_width())
        self.configure_reading_tags()

    def configure_reading_tags(self):
        """Set the reading view's styles, which plain Tk tags can't adapt to appearance alone"""
        text = self.reading_view._textbox
        scale = self.reading_view._apply_widget_scaling
        is_dark = ctk.get_appearance_mode() == "Dark"
        color = lambda pair: pair[1] if is_dark else pair[0]

        text.tag_configure(
            "book_title",
            font=(READING_FONT, -round(scale(28))),
            foreground=color(COLOR_TEXT),
            spacing1=round(scale(READING_MARGIN)),
            spacing3=round(scale(4))
        )
        text.tag_configure(
            "book_author",
            font=(UI_FONT, -round(scale(14))),
            foreground=color(COLOR_TEXT_SECONDARY),
            spacing3=round(scale(32))
        )
        text.tag_configure(
            "highlight",
            background=color(COLOR_MARKER),
            foreground=color(COLOR_TEXT)
        )
        text.tag_configure("highlight_line", spacing2=round(scale(6)))
        text.tag_configure(
            "highlight_place",
            font=(UI_FONT, -round(scale(12))),
            foreground=color(COLOR_TEXT_MUTED),
            spacing1=round(scale(8)),
            spacing3=round(scale(28))
        )

    def limit_reading_line_width(self):
        """Keep lines at a readable length, however wide the window gets"""
        scale = self.reading_view._apply_widget_scaling
        spare_width = self.reading_view._textbox.winfo_width() - round(scale(READING_MAX_LINE_WIDTH + 2 * READING_MARGIN))
        for tag in ("book_title", "book_author", "highlight_line", "highlight_place"):
            self.reading_view._textbox.tag_configure(tag, rmargin=max(0, spare_width))

    def build_export_bar(self):
        bar = ctk.CTkFrame(self.root, height=64, corner_radius=0, fg_color="transparent")
        bar.grid(row=4, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        save_to = ctk.CTkLabel(bar, text="Save to", font=ui_font(13), text_color=COLOR_TEXT_SECONDARY)
        save_to.grid(row=0, column=0, padx=(24, 4), pady=16)

        self.output_browse_button = ctk.CTkButton(
            bar,
            text="",
            command=self.browse_output_dir,
            font=ui_font(13),
            height=32,
            width=0,
            corner_radius=8,
            fg_color=COLOR_RAISED,
            hover_color=COLOR_HAIRLINE,
            text_color=COLOR_TEXT
        )
        self.output_browse_button.grid(row=0, column=1, padx=(4, 16))
        self.output_path_var.trace_add("write", lambda *args: self.refresh_output_button())
        self.refresh_output_button()

        self.script1_check = self.format_checkbox(bar, "With metadata", self.script1_var)
        self.script1_check.grid(row=0, column=3, padx=(8, 16))
        self.script2_check = self.format_checkbox(bar, "Text only", self.script2_var)
        self.script2_check.grid(row=0, column=4, padx=(0, 24))

        self.process_button = ctk.CTkButton(
            bar,
            text="Export",
            command=self.start_processing,
            font=ui_font(14, "bold"),
            height=36,
            width=148,
            corner_radius=8,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_ON_ACCENT,
            text_color_disabled=COLOR_TEXT_MUTED
        )
        self.process_button.grid(row=0, column=5, padx=(0, 24))

        self.cancel_button = ctk.CTkButton(
            bar,
            text="Cancel",
            command=self.cancel_processing,
            font=ui_font(14),
            height=36,
            width=148,
            corner_radius=8,
            fg_color=COLOR_RAISED,
            hover_color=COLOR_HAIRLINE,
            text_color=COLOR_TEXT,
            state="disabled"
        )
        self.cancel_button.grid(row=0, column=5, padx=(0, 24))
        self.cancel_button.grid_remove()

    def format_checkbox(self, master, text, variable):
        variable.trace_add("write", lambda *args: self.update_export_state())
        return ctk.CTkCheckBox(
            master,
            text=text,
            variable=variable,
            font=ui_font(13),
            text_color=COLOR_TEXT,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            border_width=1,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            border_color=COLOR_CONTROL_BORDER,
            checkmark_color=COLOR_ON_ACCENT
        )

    def build_status_bar(self):
        bar = ctk.CTkFrame(self.root, height=36, corner_radius=0, fg_color=COLOR_SIDEBAR)
        bar.grid(row=5, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bar, text="", font=ui_font(12), text_color=COLOR_TEXT_SECONDARY, height=20, anchor="w")
        self.status_label.grid(row=0, column=0, padx=(24, 8), pady=4, sticky="ew")

        self.show_folder_button = self.quiet_button(bar, "Show in Folder", self.show_output_folder)
        self.show_folder_button.grid(row=0, column=1, padx=(0, 4), pady=4)
        self.show_folder_button.grid_remove()

        self.details_button = self.quiet_button(bar, "Show Details", self.toggle_details)
        self.details_button.grid(row=0, column=2, padx=(0, 16), pady=4)

    def build_details(self):
        self.details_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.details_frame.grid(row=6, column=0, sticky="ew")
        self.details_frame.grid_columnconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            self.details_frame,
            wrap="word",
            height=160,
            corner_radius=8,
            fg_color=COLOR_PAGE,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(family=MONO_FONT, size=12),
            scrollbar_button_color=COLOR_HAIRLINE,
            scrollbar_button_hover_color=COLOR_CONTROL_BORDER
        )
        self.log_text.grid(row=0, column=0, padx=(24, 8), pady=(0, 16), sticky="ew")
        self.log_text.configure(state="disabled")

        self.clear_button = self.quiet_button(self.details_frame, "Clear", self.clear_log)
        self.clear_button.grid(row=0, column=1, padx=(0, 16), pady=(0, 16), sticky="n")
        self.details_frame.grid_remove()

    def bind_shortcuts(self):
        self.root.bind(f"<{SHORTCUT_MODIFIER}-o>", lambda event: self.browse_file())
        self.root.bind(f"<{SHORTCUT_MODIFIER}-Return>", lambda event: self.start_processing_if_ready())
        self.root.bind("<Escape>", lambda event: self.cancel_processing())
        self.root.bind("<Up>", lambda event: self.move_selection(-1))
        self.root.bind("<Down>", lambda event: self.move_selection(1))
        self.root.bind("<space>", lambda event: self.toggle_selected_book())

        # On a Mac, commands are expected in the menu bar too
        if sys.platform == "darwin":
            menu_bar = tk.Menu(self.root)
            file_menu = tk.Menu(menu_bar, tearoff=False)
            file_menu.add_command(label="Open…", accelerator="Command-O", command=self.browse_file)
            file_menu.add_command(label="Export", accelerator="Command-Return", command=self.start_processing_if_ready)
            menu_bar.add_cascade(label="File", menu=file_menu)
            self.root.configure(menu=menu_bar)

    def load_preferences(self):
        """Load saved preferences from config file"""
        self.last_output_dir = os.path.expanduser("~")
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved_dir = json.load(f).get('last_output_dir')
            if saved_dir and os.path.isdir(saved_dir):
                self.last_output_dir = saved_dir
        except (OSError, ValueError, AttributeError):
            pass

    def save_preferences(self):
        """Save preferences to config file"""
        try:
            config = {'last_output_dir': self.output_path_var.get()}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f)
        except OSError:
            pass

    def set_window_icon(self):
        """Show the Klippings logo on the window, when the logo is available"""
        is_windows = sys.platform.startswith("win")
        icon_path = asset_path("Klippings Logo.ico" if is_windows else "Klippings Logo.png")
        if not os.path.exists(icon_path):
            return
        try:
            if is_windows:
                self.root.iconbitmap(icon_path)
            else:
                self.icon_image = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            pass

    def refresh_output_button(self):
        self.output_browse_button.configure(text=shorten_path(self.output_path_var.get()))

    def browse_output_dir(self):
        """Open directory browser to select output location"""
        directory = filedialog.askdirectory(
            parent=self.root,
            title="Choose a Folder to Save To",
            initialdir=self.output_path_var.get()
        )
        if directory:
            self.output_path_var.set(directory)
            self.save_preferences()
            self.log(f"Saving to: {directory}")

    def show_drop_hover(self, hovering):
        self.empty_state.configure(border_color=COLOR_ACCENT if hovering else COLOR_PAGE)

    def drop_file(self, event):
        """Handle drag and drop file"""
        self.show_drop_hover(False)
        # Tk splits the paths and removes the braces around any containing spaces
        dropped_files = self.root.tk.splitlist(event.data)
        file_path = dropped_files[0].strip() if dropped_files else ''

        if os.path.isfile(file_path) and file_path.lower().endswith('.txt'):
            self.file_path_var.set(file_path)
            self.log(f"File dropped: {os.path.basename(file_path)}")
            if len(dropped_files) > 1:
                self.log("Several files were dropped, only the first one is used")
            self.parse_and_show_books(file_path)
        else:
            messagebox.showerror("Can't Open This File", "Klippings reads .txt files, like My Clippings.txt.", parent=self.root)

    def cancel_processing(self):
        """Cancel the current processing operation"""
        if self.is_processing:
            self.cancel_requested = True
            self.log("\nCancelling after the current file")
            self.set_status("Cancelling…")

    def browse_file(self):
        """Open file browser to select My Clippings.txt"""
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Choose My Clippings.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=os.path.expanduser("~")
        )
        if filename:
            self.file_path_var.set(filename)
            self.log(f"File selected: {os.path.basename(filename)}")
            self.parse_and_show_books(filename)

    def parse_and_show_books(self, filepath):
        """Parse the clippings file and display book selection"""
        self.log("Reading the file")

        # Clear the previous file's books so they can't be processed by mistake
        for widget in self.books_scroll_frame.winfo_children():
            widget.destroy()
        self.book_vars.clear()
        self.book_rows.clear()
        self.book_data = {}
        self.selected_title = None
        self.show_book_view(False)

        try:
            books, stats = parse_clippings(read_file_with_encoding(filepath))
        except Exception as e:
            self.log(f"Couldn't read the file: {str(e)}")
            self.set_status("Couldn't read that file")
            messagebox.showerror("Can't Read This File", f"Klippings couldn't read this file.\n\n{str(e)}", parent=self.root)
            self.update_export_state()
            return

        self.book_data = books
        self.log_parse_summary(stats)

        if not books:
            self.log("No highlights found in this file\n")
            self.set_status("No highlights found in that file")
            messagebox.showwarning(
                "No Highlights Found",
                "This file has no highlights. Check it's the My Clippings.txt from your Kindle.",
                parent=self.root
            )
            self.update_export_state()
            return

        max_count = max(len(highlights) for highlights in books.values())
        for i, (book_title, highlights) in enumerate(books.items()):
            var = tk.BooleanVar(value=True)  # Default to selected
            var.trace_add("write", lambda *args: self.update_export_state())
            self.book_vars[book_title] = var

            row = BookRow(
                self.books_scroll_frame,
                book_title,
                len(highlights),
                max_count,
                var,
                lambda title=book_title: self.select_book(title)
            )
            row.grid(row=i, column=0, padx=(0, 4), pady=(0, 2), sticky="ew")
            self.book_rows[book_title] = row

        highlight_total = sum(len(highlights) for highlights in books.values())
        self.book_summary_label.configure(text=f"{format_count(len(books), 'book')}, {format_count(highlight_total, 'highlight')}")
        self.file_label.configure(text=os.path.basename(filepath))
        self.show_book_view(True)
        self.select_book(next(iter(books)))
        self.update_export_state()
        self.root.after_idle(self.refresh_book_scrollbar)

        skipped_total = sum(stats[key] for key in SKIPPED_ENTRY_LABELS)
        if skipped_total:
            self.set_status(f"{skipped_total:,} {'entry' if skipped_total == 1 else 'entries'} left out, see details")
        else:
            self.set_status("Ready to export")
        self.log(f"Found {format_count(len(books), 'book')}\n")

    def refresh_book_scrollbar(self):
        """Only show the book list's scrollbar when there's more to scroll to"""
        fits = self.books_scroll_frame._parent_canvas.yview() == (0.0, 1.0)
        self.books_scroll_frame.configure(scrollbar_button_color=COLOR_SIDEBAR if fits else COLOR_HAIRLINE)

    def show_book_view(self, visible):
        if visible:
            self.empty_state.grid_remove()
            self.book_selection_frame.grid()
            self.change_file_button.grid()
        else:
            self.book_selection_frame.grid_remove()
            self.change_file_button.grid_remove()
            self.file_label.configure(text="")
            self.empty_state.grid()

    def select_book(self, title):
        """Show a book's highlights in the reading view"""
        for row_title, row in self.book_rows.items():
            row.set_selected(row_title == title)
        self.selected_title = title
        self.render_book(title)

    def render_book(self, title):
        highlights = self.book_data[title]
        view = self.reading_view
        view.configure(state="normal")
        view.delete("1.0", "end")

        view.insert("end", f"{title}\n", "book_title")
        author = highlights[0][1]
        view.insert("end", f"{author}\n" if author else "\n", "book_author")

        for highlight_text, _, page_info, location in highlights:
            for line in highlight_text.split("\n"):
                if line:
                    view.insert("end", line, ("highlight", "highlight_line"))
                view.insert("end", "\n", "highlight_line")
            view.insert("end", format_place(page_info, location) + "\n", "highlight_place")

        view.configure(state="disabled")
        view.yview_moveto(0)
        self.limit_reading_line_width()

    def move_selection(self, step):
        if not self.selected_title:
            return
        titles = list(self.book_rows)
        index = titles.index(self.selected_title) + step
        if 0 <= index < len(titles):
            self.select_book(titles[index])

    def toggle_selected_book(self):
        if self.selected_title:
            var = self.book_vars[self.selected_title]
            var.set(not var.get())

    def log_parse_summary(self, stats):
        """Log what was found in the clippings file and what was left out"""
        self.log(f"  Highlights: {stats['highlight']:,}")
        for key, label in SKIPPED_ENTRY_LABELS.items():
            if stats[key]:
                self.log(f"  Skipped {label}: {stats[key]:,}")

    def toggle_all_books(self):
        if all(var.get() for var in self.book_vars.values()):
            self.select_none_books()
        else:
            self.select_all_books()

    def select_all_books(self):
        """Select all books"""
        for var in self.book_vars.values():
            var.set(True)
        self.log("All books selected")

    def select_none_books(self):
        """Deselect all books"""
        for var in self.book_vars.values():
            var.set(False)
        self.log("All books deselected")

    def update_export_state(self):
        """Keep the export button's label and availability in step with the choices made"""
        selected_count = sum(1 for var in self.book_vars.values() if var.get())
        all_selected = bool(self.book_vars) and selected_count == len(self.book_vars)
        self.toggle_all_button.configure(text="Select None" if all_selected else "Select All")

        if self.is_processing:
            return

        if self.script1_var.get():
            label = f"Export {format_count(selected_count, 'Book')}" if selected_count else "Export"
            enabled = selected_count > 0
        elif self.script2_var.get():
            label = "Simplify Folder"
            enabled = True
        else:
            label = "Export"
            enabled = False

        self.process_button.configure(
            text=label,
            state="normal" if enabled else "disabled",
            fg_color=COLOR_ACCENT if enabled else COLOR_RAISED
        )

    def set_status(self, message, show_folder=False):
        self.status_label.configure(text=message)
        if show_folder:
            self.show_folder_button.grid()
        else:
            self.show_folder_button.grid_remove()

    def show_output_folder(self):
        if self.last_output_dir_used:
            open_folder(self.last_output_dir_used)

    def toggle_details(self):
        if self.details_frame.winfo_ismapped():
            self.details_frame.grid_remove()
            self.details_button.configure(text="Show Details")
        else:
            self.show_details()

    def show_details(self):
        self.details_frame.grid()
        self.details_button.configure(text="Hide Details")

    def log(self, message):
        """Add message to log, from any thread"""
        self.run_on_ui(lambda: self.append_log(message))

    def append_log(self, message):
        """Write a message to the log widget"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def run_on_ui(self, callback):
        """Queue a callback for the UI thread, as Tk isn't safe to use from others"""
        self.ui_queue.put(callback)

    def poll_ui_queue(self):
        """Run callbacks queued for the UI thread"""
        try:
            while not self.closing:
                self.ui_queue.get_nowait()()
        except queue.Empty:
            pass
        finally:
            if not self.closing:
                self.refresh_appearance()
                self.root.after(UI_POLL_INTERVAL_MS, self.poll_ui_queue)

    def refresh_appearance(self):
        """Restyle the reading view when the system switches between light and dark"""
        appearance_mode = ctk.get_appearance_mode()
        if appearance_mode != self.appearance_mode:
            self.appearance_mode = appearance_mode
            self.configure_reading_tags()

    def clear_log(self):
        """Clear the log"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def validate_prerequisites(self):
        """Check if required files exist"""
        if self.script1_var.get():
            clippings_path = self.file_path_var.get()
            if clippings_path == NO_FILE_SELECTED or not clippings_path:
                messagebox.showerror(
                    "No File Chosen",
                    "Choose your My Clippings.txt file first.",
                    parent=self.root
                )
                return False
            if not os.path.exists(clippings_path):
                messagebox.showerror(
                    "File Not Found",
                    f"This file has moved or been deleted:\n\n{clippings_path}",
                    parent=self.root
                )
                return False

            # Check if any books are selected
            if not self.book_data:
                messagebox.showerror(
                    "No Highlights Found",
                    "The chosen file has no highlights. Choose a different My Clippings.txt file.",
                    parent=self.root
                )
                return False

            selected_count = sum(1 for var in self.book_vars.values() if var.get())
            if selected_count == 0:
                messagebox.showwarning(
                    "No Books Selected",
                    "Select at least one book to export.",
                    parent=self.root
                )
                return False

        # Check output directory
        output_dir = self.output_path_var.get()
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showerror(
                "Folder Not Found",
                "Choose a folder to save to.",
                parent=self.root
            )
            return False

        if self.script2_var.get() and not self.script1_var.get():
            highlights_dir = os.path.join(output_dir, RAW_DIR_NAME)
            if not os.path.isdir(highlights_dir):
                messagebox.showerror(
                    "Nothing to Simplify",
                    f"There's no {RAW_DIR_NAME} folder here yet. Turn on With metadata to create it, or choose a different folder.",
                    parent=self.root
                )
                return False

        return True

    def start_processing_if_ready(self):
        if not self.is_processing and self.process_button.cget("state") == "normal":
            self.start_processing()

    def start_processing(self):
        """Start the processing in a separate thread"""
        if not (self.script1_var.get() or self.script2_var.get()):
            messagebox.showwarning(
                "Nothing to Export",
                "Turn on With metadata, Text only, or both.",
                parent=self.root
            )
            return

        if not self.validate_prerequisites():
            return

        # The worker thread can't read Tk variables, so it gets a snapshot of them
        options = {
            'run_step1': self.script1_var.get(),
            'run_step2': self.script2_var.get(),
            'output_base': self.output_path_var.get(),
            'clippings_name': os.path.basename(self.file_path_var.get()),
            'books': {title: data for title, data in self.book_data.items() if self.book_vars[title].get()},
            'all_titles': list(self.book_data)
        }

        self.is_processing = True
        self.cancel_requested = False
        self.process_button.configure(state="disabled")
        self.process_button.grid_remove()
        self.cancel_button.configure(state="normal")
        self.cancel_button.grid()
        self.set_status("Exporting…")

        self.worker = threading.Thread(target=self.run_processing, args=(options,))
        self.worker.daemon = True
        self.worker.start()

    def run_step1(self, options, raw_dir):
        """Export the selected books, returning the paths of the files written"""
        self.log("\nExporting with metadata")
        self.log(f"Reading: {options['clippings_name']}")
        self.log(f"Processing {len(options['books'])} of {len(options['all_titles'])} books")

        results = save_highlights_to_files(
            options['books'], raw_dir, options['all_titles'], lambda: self.cancel_requested
        )

        self.log(f"Saved {format_count(len(results), 'book')}:")
        for title, count, _ in results:
            self.log(f"  {title}: {format_count(count, 'highlight')}")

        if not self.cancel_requested:
            self.log(f"Saved to: {raw_dir}")
        return [path for _, _, path in results]

    def run_step2(self, simple_dir, file_paths):
        """Simplify the given book files, returning how many were simplified"""
        self.log("\nExporting text only")

        simplified_count = 0
        for file_path in file_paths:
            if self.cancel_requested:
                break

            book_name = simplify_file(file_path, simple_dir)
            if book_name:
                simplified_count += 1
                self.log(f"  Simplified: {book_name}")
            else:
                self.log(f"  Skipped (not a Klippings export): {os.path.basename(file_path)}")

        if not self.cancel_requested and simplified_count:
            self.log(f"Saved to: {simple_dir}")
        return simplified_count

    def run_processing(self, options):
        """Execute selected processing steps"""
        output_base = options['output_base']
        raw_dir = os.path.join(output_base, RAW_DIR_NAME)
        simple_dir = os.path.join(output_base, SIMPLE_DIR_NAME)
        produced = []
        book_count = 0
        outcome = 'success'
        error_message = ''

        try:
            # With Step 1 on, Step 2 only touches this run's files. Alone, it takes the whole folder.
            file_paths = None
            if options['run_step1'] and not self.cancel_requested:
                file_paths = self.run_step1(options, raw_dir)
                book_count = len(file_paths)
                produced.append(RAW_DIR_NAME)

            if options['run_step2'] and not self.cancel_requested:
                if file_paths is None:
                    file_paths = [
                        os.path.join(raw_dir, name)
                        for name in sorted(os.listdir(raw_dir))
                        if name.lower().endswith('.txt')
                    ]
                simplified_count = self.run_step2(simple_dir, file_paths)
                if simplified_count:
                    book_count = max(book_count, simplified_count)
                    produced.append(SIMPLE_DIR_NAME)
                elif not self.cancel_requested:
                    self.log("\nNo highlight files were found to simplify")
                    outcome = 'nothing'

            if self.cancel_requested:
                self.log("\nCancelled. Files already saved were kept")
                outcome = 'cancelled'
            elif outcome == 'success':
                self.log("\nExport complete")

        except Exception as e:
            error_message = str(e)
            outcome = 'error'
            self.log(f"\nExport failed: {error_message}")

        finally:
            summary = f"Saved {format_count(book_count, 'book')} to {' and '.join(produced)}"
            self.run_on_ui(lambda: self.finish_processing(outcome, output_base, error_message, summary))

    def finish_processing(self, outcome, output_base, error_message, summary):
        """Restore the controls and tell the user how the run went"""
        self.is_processing = False
        self.cancel_requested = False
        self.cancel_button.configure(state="disabled")
        self.cancel_button.grid_remove()
        self.process_button.grid()
        self.update_export_state()
        self.last_output_dir_used = output_base

        if outcome == 'success':
            self.set_status(summary, show_folder=True)
        elif outcome == 'cancelled':
            self.set_status("Export cancelled. Files already saved were kept", show_folder=True)
        elif outcome == 'nothing':
            self.set_status("Nothing to simplify")
            messagebox.showwarning(
                "Nothing to Simplify",
                f"There are no highlight files to simplify in:\n\n{os.path.join(output_base, RAW_DIR_NAME)}",
                parent=self.root
            )
        elif outcome == 'error':
            self.set_status("Export failed")
            self.show_details()
            messagebox.showerror(
                "Export Failed",
                f"Klippings couldn't finish the export.\n\n{error_message}",
                parent=self.root
            )

    def on_closing(self):
        """Handle window closing"""
        self.closing = True
        self.cancel_requested = True

        # Let the file being written finish so it isn't left incomplete
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=WORKER_CLOSE_TIMEOUT_SECONDS)

        # Destroying the hidden root window also destroys this one
        if self._tk_root:
            self._tk_root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """Start the GUI"""
        if self._tk_root:
            self._tk_root.mainloop()
        else:
            self.root.mainloop()


def main():
    app = KindleHighlightsGUI()
    app.run()
