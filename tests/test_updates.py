"""Tests for the manual update check."""

import io
import json

import pytest

from klippings import updates


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def opener_returning(payload, requests=None):
    def opener(request, timeout):
        if requests is not None:
            requests.append((request, timeout))
        return FakeResponse(json.dumps(payload).encode("utf-8"))
    return opener


@pytest.mark.parametrize("text, expected", [
    ("v1.2.3", (1, 2, 3)),
    ("1.10.0", (1, 10, 0)),
    ("0.0.0.dev0", None),
    ("v1.2", None),
    ("latest", None),
])
def test_parse_version(text, expected):
    assert updates.parse_version(text) == expected


def test_development_version_is_detected():
    assert updates.is_development_version("0.0.0.dev0")
    assert not updates.is_development_version("1.4.0")


@pytest.mark.parametrize("latest, current, expected", [
    ("v1.4.0", "1.3.9", True),
    ("v1.10.0", "1.9.0", True),   # compared as numbers, not text
    ("v1.3.0", "1.3.0", False),
    ("v1.2.0", "1.3.0", False),
    ("v1.4.0", "0.0.0.dev0", False),
])
def test_is_newer(latest, current, expected):
    assert updates.is_newer(latest, current) is expected


def test_fetch_sends_one_get_with_no_data():
    requests = []
    tag, url = updates.fetch_latest_release(
        "1.3.0",
        opener=opener_returning(
            {"tag_name": "v1.4.0", "html_url": "https://github.com/TariqMK/Klippings/releases/tag/v1.4.0"},
            requests,
        ),
    )
    assert (tag, url) == ("v1.4.0", "https://github.com/TariqMK/Klippings/releases/tag/v1.4.0")
    request, timeout = requests[0]
    assert len(requests) == 1
    assert request.get_method() == "GET"
    assert request.data is None
    assert request.full_url == updates.LATEST_RELEASE_URL
    assert request.get_header("User-agent") == "Klippings/1.3.0"
    assert timeout == updates.REQUEST_TIMEOUT_SECONDS


def test_fetch_falls_back_to_releases_page_for_unexpected_link():
    _, url = updates.fetch_latest_release(
        "1.3.0", opener=opener_returning({"tag_name": "v1.4.0", "html_url": "https://example.com/"})
    )
    assert url == updates.RELEASES_PAGE_URL


def test_fetch_rejects_release_without_version_tag():
    with pytest.raises(ValueError):
        updates.fetch_latest_release("1.3.0", opener=opener_returning({"message": "Not Found"}))


def test_fetch_passes_on_network_errors():
    def offline(request, timeout):
        raise OSError("no connection")

    with pytest.raises(OSError):
        updates.fetch_latest_release("1.3.0", opener=offline)
