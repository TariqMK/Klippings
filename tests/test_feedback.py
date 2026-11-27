"""Tests for the Report a Problem link."""

from klippings import feedback


def test_report_url_has_only_template_version_and_os():
    url = feedback.report_problem_url("2.5.6", "macOS 26.1")
    assert url == "https://github.com/TariqMK/Klippings/issues/new?template=bug.yml&version=2.5.6&os=macOS%2026.1"


def test_development_version_goes_in_as_it_is():
    url = feedback.report_problem_url("0.0.0.dev0", "Windows 11")
    assert "version=0.0.0.dev0" in url and "os=Windows%2011" in url


def test_odd_characters_are_encoded():
    url = feedback.report_problem_url("1.0.0-new&sync.1", "Ubuntu 24.04 LTS (Noble)")
    assert "&sync" not in url
    assert "version=1.0.0-new%26sync.1" in url
    assert "os=Ubuntu%2024.04%20LTS%20%28Noble%29" in url


def test_idea_url():
    assert feedback.suggest_idea_url().endswith("/issues/new?template=idea.yml")
