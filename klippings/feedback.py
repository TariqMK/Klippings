"""Report a Problem: opens Klippings' GitHub bug form in the browser with only the version and OS filled in.

Nothing is sent from the app. The user reads the report on GitHub and decides whether to submit it.
"""

import urllib.parse

ISSUES_URL = "https://github.com/TariqMK/Klippings/issues/new"


def report_problem_url(version, os_name):
    """The bug form's address, with the version and OS URL-encoded. Nothing else goes in it."""
    query = urllib.parse.urlencode({"template": "bug.yml", "version": version, "os": os_name}, quote_via=urllib.parse.quote)
    return f"{ISSUES_URL}?{query}"


def suggest_idea_url():
    return f"{ISSUES_URL}?template=idea.yml"
