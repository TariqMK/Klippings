"""Klippings desktop GUI."""

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import os
import queue
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

NO_FILE_SELECTED = "No file selected - Click Browse or drag & drop file here"
UI_POLL_INTERVAL_MS = 50
WORKER_CLOSE_TIMEOUT_SECONDS = 5
LOG_FONT_FAMILIES = {"win32": "Consolas", "darwin": "Menlo"}
SKIPPED_ENTRY_LABELS = {
    'duplicate': "exact duplicates",
    'note': "notes",
    'bookmark': "bookmarks",
    'clip': "article clips",
    'empty': "empty highlights",
    'clipping_limit': "clipping limit messages",
    'unrecognised': "unrecognised entries"
}


def asset_path(file_name):
    """Locate a bundled asset, both from source and in a PyInstaller build"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(getattr(sys, "_MEIPASS", project_root), "assets", file_name)


class MainScrollFrame(ctk.CTkScrollableFrame):
    """Page scroller that leaves the mouse wheel to the book list under the pointer"""
    book_list = None

    def _check_if_valid_scroll(self, widget):
        if self.book_list is not None and widget == self.book_list._parent_canvas:
            return False
        return super()._check_if_valid_scroll(widget)


class KindleHighlightsGUI:
    def __init__(self):
        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
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
        self.root.geometry("900x820")
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

        # Configure grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create main scrollable frame that contains everything
        self.main_scroll_frame = MainScrollFrame(
            self.root,
            fg_color="transparent"
        )
        self.main_scroll_frame.grid(row=0, column=0, sticky="nsew")
        self.main_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        self.title_frame = ctk.CTkFrame(self.main_scroll_frame, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, padx=40, pady=(24, 2), sticky="w")

        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text="Klippings",
            font=ctk.CTkFont(size=36, weight="bold")
        )
        self.title_label.grid(row=0, column=0)

        # Version
        self.version_label = ctk.CTkLabel(
            self.title_frame,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=14),
            text_color=("gray60", "gray45")
        )
        self.version_label.grid(row=0, column=1, padx=(10, 0), pady=(0, 5), sticky="s")

        # Secondary title
        self.secondary_label = ctk.CTkLabel(
            self.main_scroll_frame,
            text="Kindle Highlights Processor",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("gray60", "gray55")
        )
        self.secondary_label.grid(row=1, column=0, padx=40, pady=(0, 2), sticky="w")

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.main_scroll_frame,
            text="Parse and simplify your Kindle highlights",
            font=ctk.CTkFont(size=13),
            text_color=("gray70", "gray45")
        )
        self.subtitle_label.grid(row=2, column=0, padx=40, pady=(0, 14), sticky="w")
        
        # File selection frame
        self.file_frame = ctk.CTkFrame(self.main_scroll_frame, corner_radius=15)
        self.file_frame.grid(row=3, column=0, padx=40, pady=(0, 12), sticky="ew")
        self.file_frame.grid_columnconfigure(1, weight=1)
        
        file_title = ctk.CTkLabel(
            self.file_frame,
            text="My Clippings File",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        file_title.grid(row=0, column=0, columnspan=3, padx=20, pady=(14, 10), sticky="w")
        
        # File path display
        self.file_path_var = tk.StringVar(value=NO_FILE_SELECTED)
        self.file_path_entry = ctk.CTkEntry(
            self.file_frame,
            textvariable=self.file_path_var,
            font=ctk.CTkFont(size=13),
            height=38,
            state="readonly",
            fg_color=("gray85", "gray20")
        )
        self.file_path_entry.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 14), sticky="ew")
        
        # Enable drag and drop if available
        if TkinterDnD and DND_FILES:
            self.file_path_entry.drop_target_register(DND_FILES)
            self.file_path_entry.dnd_bind('<<Drop>>', self.drop_file)
        
        # Browse button
        self.browse_button = ctk.CTkButton(
            self.file_frame,
            text="📁 Browse",
            command=self.browse_file,
            font=ctk.CTkFont(size=13, weight="bold"),
            width=110,
            height=38,
            corner_radius=10,
            fg_color=("#3b8ed0", "#1f6aa5"),
            hover_color=("#36719f", "#144870")
        )
        self.browse_button.grid(row=1, column=2, padx=(8, 20), pady=(0, 14), sticky="e")
        
        # Book selection frame (initially hidden)
        self.book_selection_frame = ctk.CTkFrame(self.main_scroll_frame, corner_radius=15)
        self.book_selection_frame.grid(row=4, column=0, padx=40, pady=(0, 12), sticky="ew")
        self.book_selection_frame.grid_columnconfigure(0, weight=1)
        self.book_selection_frame.grid_remove()  # Hidden by default
        
        book_selection_title = ctk.CTkLabel(
            self.book_selection_frame,
            text="Select Books to Process",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        book_selection_title.grid(row=0, column=0, padx=20, pady=(14, 8), sticky="w")
        
        # Buttons for select all/none
        self.book_buttons_frame = ctk.CTkFrame(self.book_selection_frame, fg_color="transparent")
        self.book_buttons_frame.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")
        
        self.select_all_button = ctk.CTkButton(
            self.book_buttons_frame,
            text="Select All",
            command=self.select_all_books,
            font=ctk.CTkFont(size=12),
            width=100,
            height=30,
            corner_radius=8,
            fg_color=("#3b8ed0", "#1f6aa5"),
            hover_color=("#36719f", "#144870")
        )
        self.select_all_button.grid(row=0, column=0, padx=(0, 5))
        
        self.select_none_button = ctk.CTkButton(
            self.book_buttons_frame,
            text="Select None",
            command=self.select_none_books,
            font=ctk.CTkFont(size=12),
            width=100,
            height=30,
            corner_radius=8,
            fg_color=("gray60", "gray30"),
            hover_color=("gray50", "gray25")
        )
        self.select_none_button.grid(row=0, column=1, padx=5)
        
        # Scrollable frame for book checkboxes
        self.books_scroll_frame = ctk.CTkScrollableFrame(
            self.book_selection_frame,
            height=160,
            corner_radius=10,
            fg_color=("gray90", "gray17")
        )
        self.books_scroll_frame.grid(row=2, column=0, padx=20, pady=(0, 14), sticky="ew")
        self.books_scroll_frame.grid_columnconfigure(0, weight=1)
        self.main_scroll_frame.book_list = self.books_scroll_frame
        
        # Dictionary to store book checkboxes
        self.book_vars = {}
        self.book_data = {}  # Store full book data
        
        # Output directory frame
        self.output_frame = ctk.CTkFrame(self.main_scroll_frame, corner_radius=15)
        self.output_frame.grid(row=5, column=0, padx=40, pady=(0, 12), sticky="ew")
        self.output_frame.grid_columnconfigure(1, weight=1)
        
        output_title = ctk.CTkLabel(
            self.output_frame,
            text="Output Directory",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        output_title.grid(row=0, column=0, columnspan=3, padx=20, pady=(14, 10), sticky="w")
        
        # Output directory display
        self.output_path_var = tk.StringVar(value=self.last_output_dir)
        self.output_path_entry = ctk.CTkEntry(
            self.output_frame,
            textvariable=self.output_path_var,
            font=ctk.CTkFont(size=13),
            height=38,
            state="readonly",
            fg_color=("gray85", "gray20")
        )
        self.output_path_entry.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 14), sticky="ew")
        
        # Browse output button
        self.output_browse_button = ctk.CTkButton(
            self.output_frame,
            text="📂 Browse",
            command=self.browse_output_dir,
            font=ctk.CTkFont(size=13, weight="bold"),
            width=110,
            height=38,
            corner_radius=10,
            fg_color=("#3b8ed0", "#1f6aa5"),
            hover_color=("#36719f", "#144870")
        )
        self.output_browse_button.grid(row=1, column=2, padx=(8, 20), pady=(0, 14), sticky="e")
        
        # Processing options frame
        self.options_frame = ctk.CTkFrame(self.main_scroll_frame, corner_radius=15)
        self.options_frame.grid(row=6, column=0, padx=40, pady=(0, 12), sticky="ew")
        
        options_title = ctk.CTkLabel(
            self.options_frame,
            text="Select Processing Steps",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        options_title.grid(row=0, column=0, padx=20, pady=(14, 10), sticky="w")
        
        # Checkboxes for each script
        self.script1_var = tk.BooleanVar(value=True)
        self.script1_check = ctk.CTkCheckBox(
            self.options_frame,
            text="Parse My Clippings.txt → Individual book files",
            variable=self.script1_var,
            font=ctk.CTkFont(size=14),
            checkbox_width=24,
            checkbox_height=24
        )
        self.script1_check.grid(row=1, column=0, padx=20, pady=7, sticky="w")
        
        self.script2_var = tk.BooleanVar(value=True)
        self.script2_check = ctk.CTkCheckBox(
            self.options_frame,
            text="Simplify highlights (remove metadata)",
            variable=self.script2_var,
            font=ctk.CTkFont(size=14),
            checkbox_width=24,
            checkbox_height=24
        )
        self.script2_check.grid(row=2, column=0, padx=20, pady=(7, 14), sticky="w")
        
        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self.main_scroll_frame, fg_color="transparent")
        self.buttons_frame.grid(row=7, column=0, padx=40, pady=(0, 12), sticky="ew")
        self.buttons_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Process button
        self.process_button = ctk.CTkButton(
            self.buttons_frame,
            text="▶ Start Processing",
            command=self.start_processing,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            corner_radius=12,
            fg_color=("#2fa572", "#1a7a4a"),
            hover_color=("#26885f", "#156038")
        )
        self.process_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            self.buttons_frame,
            text="⏹ Cancel",
            command=self.cancel_processing,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=46,
            corner_radius=12,
            fg_color=("#d32f2f", "#b71c1c"),
            hover_color=("#c62828", "#a71a1a"),
            state="disabled"
        )
        self.cancel_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")
        
        # Console/Log frame
        self.log_frame = ctk.CTkFrame(self.main_scroll_frame, corner_radius=15)
        self.log_frame.grid(row=8, column=0, padx=40, pady=(0, 8), sticky="ew")
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        log_title = ctk.CTkLabel(
            self.log_frame,
            text="Processing Log",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_title.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="w")
        
        # Text widget for log output with fixed height
        self.log_text = ctk.CTkTextbox(
            self.log_frame,
            wrap="word",
            font=ctk.CTkFont(family=LOG_FONT_FAMILIES.get(sys.platform, "DejaVu Sans Mono"), size=12),
            corner_radius=10,
            height=220
        )
        self.log_text.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="ew")
        
        # Clear log button (below log frame)
        self.clear_button = ctk.CTkButton(
            self.main_scroll_frame,
            text="Clear Log",
            command=self.clear_log,
            font=ctk.CTkFont(size=14),
            height=40,
            corner_radius=10,
            fg_color=("gray55", "gray25"),
            hover_color=("gray45", "gray20")
        )
        self.clear_button.grid(row=9, column=0, padx=40, pady=(0, 24), sticky="ew")
        
        # Initial message
        self.log("┌─────────────────────────────────┐")
        self.log("│  Welcome to Klippings!          │")
        self.log("└─────────────────────────────────┘\n")
        self.log("📋 Instructions:")
        self.log("  1. Select 'My Clippings.txt' (Browse or drag & drop)")
        self.log("  2. Choose output directory (remembers last selection)")
        self.log("  3. Select processing steps and click 'Start Processing'\n")
        if not TkinterDnD:
            self.log("⚠️  Drag & drop not available (tkinterdnd2 not installed)")
            self.log("   Install with: pip install tkinterdnd2\n")
        self.log("Ready to process your highlights! ✨\n")
        self.poll_ui_queue()
        
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

    def browse_output_dir(self):
        """Open directory browser to select output location"""
        directory = filedialog.askdirectory(
            parent=self.root,
            title="Select Output Directory",
            initialdir=self.output_path_var.get()
        )
        if directory:
            self.output_path_var.set(directory)
            self.save_preferences()
            self.log(f"📂 Output directory: {directory}")

    def drop_file(self, event):
        """Handle drag and drop file"""
        # Tk splits the paths and removes the braces around any containing spaces
        dropped_files = self.root.tk.splitlist(event.data)
        file_path = dropped_files[0].strip() if dropped_files else ''

        if os.path.isfile(file_path) and file_path.lower().endswith('.txt'):
            self.file_path_var.set(file_path)
            self.log(f"📁 File dropped: {os.path.basename(file_path)}")
            if len(dropped_files) > 1:
                self.log("⚠️  Several files were dropped, only the first one is used")
            self.parse_and_show_books(file_path)
        else:
            messagebox.showerror("Invalid File", "Please drop a valid .txt file", parent=self.root)

    def cancel_processing(self):
        """Cancel the current processing operation"""
        if self.is_processing:
            self.cancel_requested = True
            self.log("\n⚠️  Cancellation requested... stopping after current file")

    def browse_file(self):
        """Open file browser to select My Clippings.txt"""
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Select My Clippings.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=os.path.expanduser("~")
        )
        if filename:
            self.file_path_var.set(filename)
            self.log(f"📁 File selected: {os.path.basename(filename)}")
            self.parse_and_show_books(filename)

    def parse_and_show_books(self, filepath):
        """Parse the clippings file and display book selection"""
        self.log("📖 Parsing books from file...")

        # Clear the previous file's books so they can't be processed by mistake
        for widget in self.books_scroll_frame.winfo_children():
            widget.destroy()
        self.book_vars.clear()
        self.book_data = {}
        self.book_selection_frame.grid_remove()

        try:
            books, stats = parse_clippings(read_file_with_encoding(filepath))
        except Exception as e:
            self.log(f"✗ Error parsing books: {str(e)}")
            messagebox.showerror("Parse Error", f"Could not parse books:\n{str(e)}", parent=self.root)
            return

        self.book_data = books

        # Create checkboxes for each book
        for i, (book_title, highlights) in enumerate(books.items()):
            var = tk.BooleanVar(value=True)  # Default to selected
            self.book_vars[book_title] = var

            # Create checkbox with book title and highlight count
            checkbox = ctk.CTkCheckBox(
                self.books_scroll_frame,
                text=f"{book_title} ({len(highlights)} highlights)",
                variable=var,
                font=ctk.CTkFont(size=13),
                checkbox_width=22,
                checkbox_height=22
            )
            checkbox.grid(row=i, column=0, padx=15, pady=5, sticky="w")

        self.log_parse_summary(stats)

        if not books:
            self.log("✗ No highlights found in this file.\n")
            messagebox.showwarning(
                "No Highlights Found",
                "⚠️ No highlights were found in this file.\n\nPlease check it's a Kindle 'My Clippings.txt' file.",
                parent=self.root
            )
            return

        # Show the book selection frame
        self.book_selection_frame.grid()
        self.log(f"✓ Found {len(books)} books. Select which ones to process.\n")

    def log_parse_summary(self, stats):
        """Log what was found in the clippings file and what was left out"""
        self.log(f"  Highlights: {stats['highlight']}")
        for key, label in SKIPPED_ENTRY_LABELS.items():
            if stats[key]:
                self.log(f"  Skipped {label}: {stats[key]}")

    def select_all_books(self):
        """Select all books"""
        for var in self.book_vars.values():
            var.set(True)
        self.log("✓ All books selected")

    def select_none_books(self):
        """Deselect all books"""
        for var in self.book_vars.values():
            var.set(False)
        self.log("○ All books deselected")

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
                self.root.after(UI_POLL_INTERVAL_MS, self.poll_ui_queue)

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
                    "Missing File",
                    "❌ No file selected!\n\nPlease browse or drag & drop your 'My Clippings.txt' file.",
                    parent=self.root
                )
                return False
            if not os.path.exists(clippings_path):
                messagebox.showerror(
                    "File Not Found",
                    f"❌ Selected file not found:\n\n{clippings_path}",
                    parent=self.root
                )
                return False

            # Check if any books are selected
            if not self.book_data:
                messagebox.showerror(
                    "No Highlights Found",
                    "❌ No highlights were found in the selected file.\n\nPlease select a different 'My Clippings.txt' file.",
                    parent=self.root
                )
                return False

            selected_count = sum(1 for var in self.book_vars.values() if var.get())
            if selected_count == 0:
                messagebox.showwarning(
                    "No Books Selected",
                    "⚠️ Please select at least one book to process.",
                    parent=self.root
                )
                return False

        # Check output directory
        output_dir = self.output_path_var.get()
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showerror(
                "Invalid Output Directory",
                "❌ Please select a valid output directory!",
                parent=self.root
            )
            return False

        if self.script2_var.get() and not self.script1_var.get():
            highlights_dir = os.path.join(output_dir, RAW_DIR_NAME)
            if not os.path.isdir(highlights_dir):
                messagebox.showerror(
                    "Missing Folder",
                    f"❌ {RAW_DIR_NAME} folder not found!\n\nPlease run Step 1 first or enable it.",
                    parent=self.root
                )
                return False

        return True

    def start_processing(self):
        """Start the processing in a separate thread"""
        if not (self.script1_var.get() or self.script2_var.get()):
            messagebox.showwarning(
                "No Steps Selected",
                "⚠️ Please select at least one processing step!",
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
        self.process_button.configure(state="disabled", text="⏳ Processing...")
        self.cancel_button.configure(state="normal")

        self.worker = threading.Thread(target=self.run_processing, args=(options,))
        self.worker.daemon = True
        self.worker.start()

    def run_step1(self, options, raw_dir):
        """Export the selected books, returning the paths of the files written"""
        self.log("\n" + "═" * 63)
        self.log("STEP 1: Parsing My Clippings.txt")
        self.log("═" * 63)
        self.log(f"Reading: {options['clippings_name']}")
        self.log(f"Processing {len(options['books'])} of {len(options['all_titles'])} books...")

        results = save_highlights_to_files(
            options['books'], raw_dir, options['all_titles'], lambda: self.cancel_requested
        )

        self.log(f"\n✓ Saved {len(results)} books:")
        for title, count, _ in results:
            self.log(f"  • {title}: {count} highlights")

        if not self.cancel_requested:
            self.log(f"\n✓ Step 1 completed! Files saved to: {raw_dir}")
        return [path for _, _, path in results]

    def run_step2(self, simple_dir, file_paths):
        """Simplify the given book files, returning how many were simplified"""
        self.log("\n" + "═" * 63)
        self.log("STEP 2: Simplifying Highlights")
        self.log("═" * 63)

        simplified_count = 0
        for file_path in file_paths:
            if self.cancel_requested:
                break

            book_name = simplify_file(file_path, simple_dir)
            if book_name:
                simplified_count += 1
                self.log(f"  ✓ Simplified: {book_name}")
            else:
                self.log(f"  ⚠️  Skipped (not a Klippings export): {os.path.basename(file_path)}")

        if not self.cancel_requested and simplified_count:
            self.log(f"\n✓ Step 2 completed! Simplified files saved to: {simple_dir}")
        return simplified_count

    def run_processing(self, options):
        """Execute selected processing steps"""
        output_base = options['output_base']
        raw_dir = os.path.join(output_base, RAW_DIR_NAME)
        simple_dir = os.path.join(output_base, SIMPLE_DIR_NAME)
        produced = []
        outcome = 'success'
        error_message = ''

        try:
            # With Step 1 on, Step 2 only touches this run's files. Alone, it takes the whole folder.
            file_paths = None
            if options['run_step1'] and not self.cancel_requested:
                file_paths = self.run_step1(options, raw_dir)
                produced.append(f"Raw highlights:        {raw_dir}")

            if options['run_step2'] and not self.cancel_requested:
                if file_paths is None:
                    file_paths = [
                        os.path.join(raw_dir, name)
                        for name in sorted(os.listdir(raw_dir))
                        if name.lower().endswith('.txt')
                    ]
                if self.run_step2(simple_dir, file_paths):
                    produced.append(f"Simplified highlights: {simple_dir}")
                elif not self.cancel_requested:
                    self.log("\n⚠️  No highlight files were found to simplify")
                    outcome = 'nothing'

            if self.cancel_requested:
                self.log("\n❌ Processing cancelled by user")
                outcome = 'cancelled'
            elif outcome == 'success':
                self.log("\n" + "═" * 63)
                self.log("🎉 ALL PROCESSING COMPLETED SUCCESSFULLY!")
                self.log("═" * 63 + "\n")
                for line in produced:
                    self.log(line)

        except Exception as e:
            error_message = str(e)
            outcome = 'error'
            self.log(f"\n\n❌ CRITICAL ERROR: {error_message}")

        finally:
            self.run_on_ui(lambda: self.finish_processing(outcome, output_base, error_message))

    def finish_processing(self, outcome, output_base, error_message):
        """Restore the controls and tell the user how the run went"""
        self.is_processing = False
        self.cancel_requested = False
        self.process_button.configure(state="normal", text="▶ Start Processing")
        self.cancel_button.configure(state="disabled")

        if outcome == 'success':
            messagebox.showinfo(
                "Success! 🎉",
                f"Processing completed successfully!\n\nCheck the output folder:\n{output_base}",
                parent=self.root
            )
        elif outcome == 'nothing':
            messagebox.showwarning(
                "Nothing Simplified",
                f"⚠️ No highlight files were found to simplify in:\n\n{os.path.join(output_base, RAW_DIR_NAME)}",
                parent=self.root
            )
        elif outcome == 'error':
            messagebox.showerror(
                "Error",
                f"An error occurred during processing:\n\n{error_message}\n\nCheck the log for details.",
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
