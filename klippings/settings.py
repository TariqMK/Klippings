"""Keep Klippings' settings in a Klippings-data folder next to the app, so the app is portable."""

import json
import os
import sys

DATA_FOLDER_NAME = "Klippings-data"
SETTINGS_FILE_NAME = "settings.json"


def app_folder(executable=None, frozen=None, package_dir=None, cwd=None):
    """Return the folder the app runs from, which holds Klippings-data"""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        # sys.executable is the real file, not the temporary folder a one-file build unpacks to
        folder = os.path.dirname(os.path.abspath(executable or sys.executable))
        # On macOS the data goes beside Klippings.app, not inside the bundle
        parts = folder.split(os.sep)
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].endswith(".app"):
                return os.sep.join(parts[:i]) or os.sep
        return folder

    # From source, use the project root
    package_dir = package_dir or os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(package_dir)
    if os.path.isfile(os.path.join(project_root, "pyproject.toml")):
        return project_root
    # Installed with pip, there is no project root, so use the folder Klippings was started from
    return os.path.abspath(cwd or os.getcwd())


def data_folder(base=None):
    return os.path.join(base or app_folder(), DATA_FOLDER_NAME)


def settings_path(base=None):
    return os.path.join(data_folder(base), SETTINGS_FILE_NAME)


def to_stored_path(path, base):
    """Store a folder inside the app folder as a relative path, so it moves with the app.
    Folders outside it stay absolute, as moving the app doesn't move them."""
    try:
        relative = os.path.relpath(path, base)
    except ValueError:
        # A different drive on Windows can't be relative
        return path
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return path
    return relative


def from_stored_path(path, base):
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))


def load_settings(base=None):
    """Return the saved settings, or an empty dict if there are none or they can't be read"""
    base = base or app_folder()
    try:
        with open(settings_path(base), "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(settings, dict):
        return {}
    if isinstance(settings.get("last_output_dir"), str) and settings["last_output_dir"]:
        settings["last_output_dir"] = from_stored_path(settings["last_output_dir"], base)
    return settings


def save_settings(settings, base=None):
    """Save the settings, creating Klippings-data the first time. Raises OSError if it can't be written."""
    base = base or app_folder()
    stored = dict(settings)
    if stored.get("last_output_dir"):
        stored["last_output_dir"] = to_stored_path(stored["last_output_dir"], base)
    os.makedirs(data_folder(base), exist_ok=True)
    with open(settings_path(base), "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2)
