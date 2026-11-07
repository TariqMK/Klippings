"""Checks GitHub for a newer Klippings release, only when the user asks."""

import json
import re
import urllib.request

LATEST_RELEASE_URL = "https://api.github.com/repos/TariqMK/Klippings/releases/latest"
RELEASES_PAGE_URL = "https://github.com/TariqMK/Klippings/releases"
REQUEST_TIMEOUT_SECONDS = 10

_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text):
    """Turn 'v1.2.3' or '1.2.3' into (1, 2, 3), or None for anything else"""
    match = _VERSION_PATTERN.match(text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def is_development_version(version):
    """Builds from source carry a version like '0.0.0.dev0' instead of a release version"""
    return parse_version(version) is None


def is_newer(latest, current):
    """True when the release version 'latest' is newer than 'current'"""
    latest_parts, current_parts = parse_version(latest), parse_version(current)
    return bool(latest_parts and current_parts and latest_parts > current_parts)


def fetch_latest_release(current_version, opener=urllib.request.urlopen):
    """Ask GitHub for the latest public release; returns (tag, page_url).

    Sends one GET request with no data. Raises OSError or ValueError on failure.
    """
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Klippings/{current_version}",
        },
    )
    with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        release = json.loads(response.read().decode("utf-8"))
    tag = release.get("tag_name")
    if not isinstance(tag, str) or parse_version(tag) is None:
        raise ValueError("GitHub returned a release without a version tag")
    page_url = release.get("html_url")
    if not isinstance(page_url, str) or not page_url.startswith("https://github.com/"):
        page_url = RELEASES_PAGE_URL
    return tag, page_url
