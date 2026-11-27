"""Tests for Klippings.log: trimming, privacy, the session header and unhandled errors."""

import logging
import os
import subprocess
import sys
import threading

import pytest

from klippings import app_log


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    """Start logging into a temporary data folder, and put the logging setup back afterwards"""
    root = logging.getLogger()
    saved = (root.handlers[:], root.level, sys.excepthook, threading.excepthook)
    monkeypatch.setattr(app_log.atexit, "register", lambda function: None)
    path = app_log.start("1.2.3", base=str(tmp_path))
    yield path
    app_log.end()
    handler = app_log._state["handler"]
    if handler:
        handler.close()
    if app_log._state["fault_file"]:
        import faulthandler
        faulthandler.disable()
        app_log._state["fault_file"].close()
    app_log._state.update(path=None, handler=None, ended=False, fault_file=None)
    root.handlers[:], root.level = saved[0], saved[1]
    sys.excepthook, threading.excepthook = saved[2], saved[3]


def read(path):
    app_log.flush()
    with open(path, encoding="utf-8") as file:
        return file.read()


def test_log_goes_in_the_data_folder(log_file, tmp_path):
    assert log_file == os.path.join(str(tmp_path), "Klippings-data", "Klippings.log")


def test_header_names_version_build_kind_and_os(log_file):
    text = read(log_file)
    assert "Klippings v1.2.3 (release, from source)" in text
    assert "OS: " in text and "Python " in text and "Data folder: " in text


def test_line_format(log_file):
    logging.getLogger("klippings.export").info("Export finished: 3 text files")
    line = read(log_file).splitlines()[-1]
    # 2026-11-18 14:03:22.481 +00:00 INFO    [export] Export finished...
    date, clock, offset, level, area = line.split()[:5]
    assert len(date) == 10 and len(clock) == 12 and offset[0] in "+-" and offset[3] == ":"
    assert level == "INFO" and area == "[export]"


def test_trimming_keeps_the_newest_whole_lines(tmp_path):
    path = tmp_path / "test.log"
    path.write_text("".join(f"old line {i}\n" for i in range(5000)), encoding="utf-8")
    handler = app_log.TrimmedFileHandler(str(path), max_bytes=20_000, keep_bytes=10_000)
    handler.setFormatter(logging.Formatter("%(message)s"))
    text = path.read_text(encoding="utf-8")
    assert text.startswith(app_log.TRIM_MARKER + "\n")
    assert text.splitlines()[1].startswith("old line ")
    assert text.rstrip().endswith("old line 4999")
    assert len(text.encode()) <= 10_000 + 40

    for i in range(2000):
        handler.emit(logging.LogRecord("t", logging.INFO, __file__, 1, f"new line {i}", None, None))
    handler.close()
    text = path.read_text(encoding="utf-8")
    assert os.path.getsize(path) <= 20_000 + 40
    assert text.startswith(app_log.TRIM_MARKER) and text.rstrip().endswith("new line 1999")


def test_home_folder_hidden_in_both_slash_directions():
    assert app_log.hide_home("/Users/alex/Documents/My Clippings.txt", "/Users/alex") == "~/Documents/My Clippings.txt"
    assert app_log.hide_home(r"C:\Users\Alex\Desktop\a.txt", r"C:\Users\Alex") == r"~\Desktop\a.txt"
    assert app_log.hide_home("c:/users/alex/Desktop", r"C:\Users\Alex") == "~/Desktop"
    # Another user whose name starts the same way is left alone
    assert app_log.hide_home("/Users/alexandra/x", "/Users/alex") == "/Users/alexandra/x"


def test_home_folder_hidden_in_tracebacks(log_file):
    home = os.path.expanduser("~")
    try:
        raise OSError(f"can't open {os.path.join(home, 'Secret', 'file.txt')}")
    except OSError:
        logging.getLogger("klippings.files").error("Read failed", exc_info=True)
    text = read(log_file)
    assert "Traceback" in text
    assert home not in text
    assert os.path.join("~", "Secret", "file.txt") in text


def test_unhandled_errors_on_main_thread_and_background_thread(log_file):
    try:
        raise ValueError("main thread boom")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    def fail():
        raise RuntimeError("worker boom")

    thread = threading.Thread(target=fail, name="Worker")
    thread.start()
    thread.join()
    text = read(log_file)
    assert "Unhandled error" in text and "ValueError: main thread boom" in text
    assert "on thread Worker" in text and "RuntimeError: worker boom" in text


def test_tk_callback_errors_reach_the_log(log_file):
    try:
        raise KeyError("button")
    except KeyError:
        app_log.log_tk_callback_error(*sys.exc_info())
    text = read(log_file)
    assert "Error in a window callback" in text and "KeyError: 'button'" in text


def test_session_end_and_crash_warning(tmp_path, monkeypatch):
    folder = tmp_path / "Klippings-data"
    folder.mkdir()
    path = folder / "Klippings.log"
    path.write_text(app_log.SESSION_START + "\nsomething\n", encoding="utf-8")
    assert not app_log.previous_session_ended(str(path))
    path.write_text(app_log.SESSION_START + "\nsomething\nx INFO [app] Session ended\n", encoding="utf-8")
    assert app_log.previous_session_ended(str(path))


def test_warning_when_previous_session_crashed(tmp_path, monkeypatch):
    folder = tmp_path / "Klippings-data"
    folder.mkdir()
    (folder / "Klippings.log").write_text(app_log.SESSION_START + "\nINFO Session started\n", encoding="utf-8")
    root = logging.getLogger()
    saved = root.handlers[:]
    monkeypatch.setattr(app_log.atexit, "register", lambda function: None)
    try:
        path = app_log.start("1.0.0", base=str(tmp_path))
        app_log.end()
        text = read(path)
    finally:
        app_log._state["handler"].close()
        import faulthandler
        faulthandler.disable()
        app_log._state["fault_file"].close()
        app_log._state.update(path=None, handler=None, ended=False, fault_file=None)
        root.handlers[:] = saved
    assert "did not close normally" in text
    assert text.rstrip().endswith(app_log.SESSION_ENDED)


def test_no_file_when_the_folder_cant_be_written(tmp_path, monkeypatch):
    blocker = tmp_path / "Klippings-data"
    blocker.write_text("a file where the folder should be")
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        assert app_log.start("1.0.0", base=str(tmp_path)) is None
        logging.getLogger("klippings.app").info("still fine")
    finally:
        root.handlers[:] = saved


@pytest.mark.parametrize("platform_name, expected", [
    ("darwin", ["open", "-R", "/a/Klippings-data/Klippings.log"]),
    ("win32", ["explorer", "/select,/a/Klippings-data/Klippings.log"]),
    ("linux", ["xdg-open", "/a/Klippings-data"]),
])
def test_view_logs_command_for_each_platform(platform_name, expected):
    assert app_log.reveal_command("/a/Klippings-data/Klippings.log", platform_name) == expected


def test_view_logs_reports_failure(tmp_path):
    path = tmp_path / "Klippings.log"
    assert app_log.reveal(str(path)) is False  # no file yet
    path.write_text("x")

    def broken_popen(command):
        raise FileNotFoundError("no file manager")

    assert app_log.reveal(str(path), popen=broken_popen) is False
    calls = []
    assert app_log.reveal(str(path), popen=calls.append) is True
    # Linux opens the folder, as most of its file managers can't select a file
    assert calls == [app_log.reveal_command(str(path))]


def test_file_manager_names():
    assert app_log.file_manager_name("darwin") == "Finder"
    assert app_log.file_manager_name("win32") == "File Explorer"
    assert app_log.file_manager_name("linux") == "the file manager"
