"""Klippings' log file: Klippings-data/Klippings.log, always on, trimmed to about the newest 1 MB.

Call start() first thing at launch, before the window. Every line has the local time with the UTC
offset, the level and the area. The home folder is written as ~. Clippings text is never logged.
If the file can't be written, the app carries on without it.
"""

import atexit
import faulthandler
import locale
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from klippings import settings

LOG_FILE_NAME = "Klippings.log"
MAX_BYTES = 1_000_000
KEEP_BYTES = 500_000
TRIM_MARKER = "--- older entries removed ---"
SESSION_START = "=" * 72
SESSION_ENDED = "Session ended"

log = logging.getLogger("klippings.app")
_state = {"path": None, "handler": None, "ended": False, "fault_file": None}


class TrimmedFileHandler(logging.FileHandler):
    """One log file that drops its oldest lines when it grows past max_bytes."""

    def __init__(self, path, max_bytes=MAX_BYTES, keep_bytes=KEEP_BYTES):
        super().__init__(path, encoding="utf-8")
        self.max_bytes, self.keep_bytes = max_bytes, keep_bytes
        self._trim()

    def emit(self, record):
        super().emit(record)
        try:
            if self.stream and os.fstat(self.stream.fileno()).st_size > self.max_bytes:
                self._trim()
        except OSError:
            pass

    def _trim(self):
        self.acquire()
        try:
            if self.stream:
                self.stream.close()
            path = Path(self.baseFilename)
            if path.exists() and path.stat().st_size > self.max_bytes:
                tail = path.read_bytes()[-self.keep_bytes:]
                tail = tail[tail.find(b"\n") + 1:]
                path.write_bytes(TRIM_MARKER.encode() + b"\n" + tail)
            self.stream = self._open()
        finally:
            self.release()


def hide_home(text, home=None):
    """Write the home folder as ~, in either slash direction and, on Windows, any case"""
    home = (home or os.path.expanduser("~")).rstrip("\\/")
    if len(home) < 2:
        return text
    pattern = r"[\\/]".join(re.escape(part) for part in re.split(r"[\\/]", home))
    flags = re.IGNORECASE if sys.platform == "win32" or re.match(r"^[A-Za-z]:", home) else 0
    return re.sub(pattern + r"(?=[\\/]|\b|$)", "~", text, flags=flags)


class PrivateFormatter(logging.Formatter):
    """Local time with milliseconds and UTC offset; the home folder shown as ~, tracebacks included"""

    def formatTime(self, record, datefmt=None):
        moment = time.localtime(record.created)
        offset = time.strftime("%z", moment) or "+0000"
        return f"{time.strftime('%Y-%m-%d %H:%M:%S', moment)}.{int(record.msecs):03d} {offset[:3]}:{offset[3:]}"

    def format(self, record):
        record.area = record.name.split(".")[-1] if record.name.startswith("klippings.") else record.name
        return hide_home(super().format(record))


FORMAT = "%(asctime)s %(levelname)-7s [%(area)s] %(message)s"


def log_path(base=None):
    return os.path.join(settings.data_folder(base), LOG_FILE_NAME)


def previous_session_ended(path):
    """True if the last session in the file ended normally, or there is none"""
    try:
        with open(path, "rb") as file:
            file.seek(max(0, os.path.getsize(path) - 64_000))
            tail = file.read().decode("utf-8", "replace")
    except OSError:
        return True
    start = tail.rfind(SESSION_START)
    if start == -1:
        return True
    return SESSION_ENDED in tail[start:]


def build_kind(version):
    frozen = getattr(sys, "frozen", False)
    kind = "development" if "dev" in version else ("branch build" if "-" in version else "release")
    return f"{kind}, {'built app' if frozen else 'from source'}"


def os_description():
    """The OS name and version as a user would say it, like 'macOS 26.1' or 'Windows 11'"""
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    if sys.platform == "win32":
        release, build = platform.release(), platform.version()
        # Windows 11 still reports release 10; build 22000 and later is 11
        if release == "10" and build.split(".")[-1].isdigit() and int(build.split(".")[-1]) >= 22000:
            release = "11"
        return f"Windows {release}"
    try:
        info = platform.freedesktop_os_release()
        return info.get("PRETTY_NAME") or f"{info.get('NAME', 'Linux')} {info.get('VERSION_ID', '')}".strip()
    except (OSError, AttributeError):
        return f"Linux {platform.release()}"


def header_lines(version):
    """Describe the app, the system and the settings, so each session explains itself"""
    lines = [
        f"Klippings v{version} ({build_kind(version)})",
        f"OS: {os_description()} ({platform.system()} {platform.release()}, {platform.version()}), {platform.machine()}",
        f"Python {platform.python_version()}",
    ]
    try:
        lang = locale.getlocale()[0] or os.environ.get("LANG", "unknown")
    except ValueError:
        lang = "unknown"
    lines.append(f"Locale: {lang}")
    lines.append(f"Data folder: {settings.data_folder()}")
    saved = settings.load_settings()
    lines.append("Settings: " + (", ".join(f"{key} = {value}" for key, value in saved.items()) or "defaults"))
    return lines


def start(version, base=None):
    """Open the log file and catch every unhandled error. Returns the log path, or None without a file."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    logging.captureWarnings(True)
    sys.excepthook = _log_unhandled
    threading.excepthook = lambda args: _log_unhandled(args.exc_type, args.exc_value, args.exc_traceback, args.thread)

    path = log_path(base)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ended = previous_session_ended(path)
        handler = TrimmedFileHandler(path)
    except OSError:
        # Logging never stops the app. View Logs explains when there is no file.
        root.addHandler(logging.NullHandler())
        return None

    handler.setFormatter(PrivateFormatter(FORMAT))
    root.addHandler(handler)
    _state.update(path=path, handler=handler, ended=False)
    handler.stream.write(SESSION_START + "\n")
    log.info("Session started")
    for line in header_lines(version):
        log.info(line)
    if not ended:
        log.warning("The previous session did not close normally (a crash or a forced quit)")

    try:
        # A hard crash in native code still leaves a trace
        _state["fault_file"] = open(path, "a", encoding="utf-8")
        faulthandler.enable(file=_state["fault_file"])
    except (OSError, ValueError, AttributeError):
        pass
    atexit.register(end)
    return path


def log_window_details(tk_root):
    """Add the Tk version and screen once the window exists"""
    try:
        log.info(
            f"Tk {tk_root.tk.call('info', 'patchlevel')}, screen {tk_root.winfo_screenwidth()} x "
            f"{tk_root.winfo_screenheight()}, scale {tk_root.winfo_fpixels('1i') / 72:.2f}"
        )
    except Exception:
        pass


def _log_unhandled(exc_type, exc_value, exc_traceback, thread=None):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    where = f" on thread {thread.name}" if thread is not None else ""
    log.error(f"Unhandled error{where}", exc_info=(exc_type, exc_value, exc_traceback))


def log_tk_callback_error(exc_type, exc_value, exc_traceback):
    """Tk's report_callback_exception, which otherwise prints to a console a windowed build lacks"""
    log.error("Error in a window callback", exc_info=(exc_type, exc_value, exc_traceback))


def end():
    """Write the last line of the session, once"""
    if _state["ended"] or not _state["handler"]:
        return
    _state["ended"] = True
    log.info(SESSION_ENDED)
    _state["handler"].flush()


def current_path():
    return _state["path"]


def flush():
    if _state["handler"]:
        _state["handler"].flush()


def reveal_command(path, platform_name=None):
    """The command that shows the log file in the system's file manager"""
    platform_name = platform_name or sys.platform
    if platform_name == "darwin":
        return ["open", "-R", path]
    if platform_name == "win32":
        return ["explorer", f"/select,{path}"]
    return ["xdg-open", os.path.dirname(path)]


def file_manager_name(platform_name=None):
    platform_name = platform_name or sys.platform
    return {"darwin": "Finder", "win32": "File Explorer"}.get(platform_name, "the file manager")


def reveal(path=None, popen=subprocess.Popen):
    """Show the log file in the file manager. Returns False if that couldn't be done."""
    flush()
    path = path or current_path()
    if not path or not os.path.isfile(path):
        return False
    try:
        # Explorer returns 1 even when it works, so the result isn't waited for or checked
        popen(reveal_command(path))
    except OSError:
        log.warning("Couldn't open the file manager to show the log file", exc_info=True)
        return False
    return True
