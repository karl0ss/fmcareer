"""The rendered report: safe data embedding, and every page actually drawing in a browser."""

import glob
import json
import os
import re
import shutil
import subprocess

import pytest

from fmcareer.render import render


def embedded(html):
    raw = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    return json.loads(raw)


def test_data_round_trips_and_cannot_close_the_script_tag(sample):
    sample["manager"]["name"] = "Evil </script><script>alert(1)</script>"
    html = render(sample)
    assert html.count("</script>") == 2  # the data block and the app script, nothing injected
    assert embedded(html)["manager"]["name"] == sample["manager"]["name"]
    assert "<title>Evil &lt;/script&gt;" in html


def chrome():
    """A headless Chromium to run the report in: FMCAREER_CHROME, PATH, or Playwright's cache."""
    if os.environ.get("FMCAREER_CHROME"):
        return os.environ["FMCAREER_CHROME"]
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome-headless-shell"):
        if shutil.which(name):
            return shutil.which(name)
    found = sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell")))
    return found[-1] if found else None


CHROME = chrome()
needs_chrome = pytest.mark.skipif(CHROME is None, reason="no headless Chromium found (set FMCAREER_CHROME)")


def dom(tmp_path, html, page):
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")
    out = subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=3000",
                          "--dump-dom", f"file://{path}#{page}"], capture_output=True, text=True, timeout=60)
    return out.stdout


def view_of(text):
    """The drawn page only: from the view up to the embedded data."""
    start = text.find('id="view"')
    return text[start:text.find('<script type="application/json"', start)]


PAGES = {
    "me": ["Alex Example", "2 clubs so far", "The climb", "Second Division Manager of the Season"],
    "seasons": ["2032/33", "First Division"],
    "season/2032-33": ["2032/33 season review", "Big City", "Not yet identified", "Old Retiree", "Partial"],
    "players": ["Sam Striker", "Gary Keeper"],
    "player/p202": ["Sam Striker", "Season by season", "£1.50M"],
    "records": ["Most goals", "Biggest signings", "5–0"],
    "honours": ["Every cup run", "National Cup"],
    "transfers": ["Every move", "Show:", "Sam Striker"],
    "club": ["Example Park", "−£250k", "Balanced 4-4-2", "live table"],
}


@needs_chrome
@pytest.mark.parametrize("page", PAGES)
def test_every_page_draws(tmp_path, sample, page):
    view = view_of(dom(tmp_path, render(sample), page))
    for expected in PAGES[page]:
        assert expected in view, f"{page}: {expected!r} missing"


@needs_chrome
def test_left_out_sections_leave_the_nav_and_fall_back(tmp_path, sample):
    sample["options"]["sections"] = ["me", "seasons"]
    text = dom(tmp_path, render(sample), "records")
    nav = text[text.find('id="nav"'):text.find("</nav>")]
    assert "Records" not in nav and "Seasons" in nav
    assert "The climb" in view_of(text)  # the hidden page falls back to the first section


@needs_chrome
def test_transfer_toggles_follow_the_report_defaults(tmp_path, sample):
    text = view_of(dom(tmp_path, render(sample), "transfers"))
    assert "Sam Striker" in text
    assert "Tom Trialist" not in text and "Staff member" not in text
    sample["options"]["show"]["Trial"] = True
    text = view_of(dom(tmp_path, render(sample), "transfers"))
    assert "Tom Trialist" in text and "Staff member" not in text
