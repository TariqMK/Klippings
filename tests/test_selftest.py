"""Tests for the --self-test that the release workflow runs on every build."""

import os
import subprocess
import sys

import pytest

from klippings import selftest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_DISPLAY = sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.mark.skipif(NO_DISPLAY, reason="Tk needs a display; CI runs the tests under xvfb-run")
def test_self_test_passes_from_source():
    pytest.importorskip("customtkinter")
    result = subprocess.run(
        [sys.executable, "-m", "klippings", "--self-test"],
        cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr
    from klippings._version import __version__
    assert result.stdout.strip().splitlines()[-1] == f"Klippings v{__version__}"


def test_missing_fonts_are_reported(monkeypatch):
    monkeypatch.setattr("klippings.images.list_fonts", lambda: {})
    problems = []
    selftest.check_fonts_and_images(problems)
    assert problems == ["No quote image fonts found"]


def test_bundled_fonts_make_images():
    problems = []
    selftest.check_fonts_and_images(problems)
    assert problems == []


def test_sample_export_works(tmp_path):
    problems = []
    selftest.check_export(problems, str(tmp_path))
    assert problems == []


def test_a_failing_check_fails_the_self_test(monkeypatch, capsys):
    def broken_window(problems):
        raise RuntimeError("no Tk")
    monkeypatch.setattr(selftest, "check_window", broken_window)
    assert selftest.run() == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert "FAIL RuntimeError: no Tk" in lines
    assert lines[-1] == "Self-test failed"


def test_no_console_does_not_crash(monkeypatch):
    # A windowed Windows build has no sys.stdout
    monkeypatch.setattr(sys, "stdout", None)
    selftest.say("Klippings v1.0.0")
