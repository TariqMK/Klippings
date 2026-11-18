"""Tests for where Klippings keeps its settings."""

import json
import os

from klippings import settings


def test_built_app_keeps_data_beside_the_executable(tmp_path):
    exe = tmp_path / "Tools" / "Klippings.exe"
    assert settings.app_folder(executable=str(exe), frozen=True) == str(tmp_path / "Tools")


def test_mac_app_keeps_data_beside_the_bundle_not_inside_it(tmp_path):
    exe = tmp_path / "Apps" / "Klippings.app" / "Contents" / "MacOS" / "Klippings"
    assert settings.app_folder(executable=str(exe), frozen=True) == str(tmp_path / "Apps")


def test_source_run_uses_the_project_root(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    package = tmp_path / "klippings"
    package.mkdir()
    assert settings.app_folder(frozen=False, package_dir=str(package)) == str(tmp_path)


def test_pip_install_uses_the_folder_it_was_started_from(tmp_path):
    package = tmp_path / "site-packages" / "klippings"
    package.mkdir(parents=True)
    start = tmp_path / "start"
    assert settings.app_folder(frozen=False, package_dir=str(package), cwd=str(start)) == str(start)


def test_nothing_is_created_until_settings_are_saved(tmp_path):
    assert settings.load_settings(str(tmp_path)) == {}
    assert not (tmp_path / settings.DATA_FOLDER_NAME).exists()


def test_settings_are_saved_in_klippings_data(tmp_path):
    output = tmp_path / "Highlights"
    output.mkdir()
    settings.save_settings({"last_output_dir": str(output)}, str(tmp_path))

    saved = tmp_path / "Klippings-data" / "settings.json"
    assert saved.is_file()
    assert settings.load_settings(str(tmp_path))["last_output_dir"] == str(output)


def test_folder_paths_are_stored_relative_so_a_move_keeps_them(tmp_path):
    old_home = tmp_path / "old"
    (old_home / "Highlights").mkdir(parents=True)
    settings.save_settings({"last_output_dir": str(old_home / "Highlights")}, str(old_home))

    stored = json.loads((old_home / "Klippings-data" / "settings.json").read_text())
    assert not os.path.isabs(stored["last_output_dir"])

    new_home = tmp_path / "new"
    os.rename(old_home, new_home)
    assert settings.load_settings(str(new_home))["last_output_dir"] == str(new_home / "Highlights")


def test_folders_outside_the_app_folder_stay_absolute(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    outside = tmp_path / "Highlights"
    outside.mkdir()
    settings.save_settings({"last_output_dir": str(outside)}, str(app))

    stored = json.loads((app / "Klippings-data" / "settings.json").read_text())
    assert stored["last_output_dir"] == str(outside)


def test_unreadable_settings_are_ignored(tmp_path):
    data = tmp_path / "Klippings-data"
    data.mkdir()
    (data / "settings.json").write_text("not json")
    assert settings.load_settings(str(tmp_path)) == {}

    (data / "settings.json").write_text("[1, 2]")
    assert settings.load_settings(str(tmp_path)) == {}
