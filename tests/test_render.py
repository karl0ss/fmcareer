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


def test_footer_shows_the_version_and_links_the_repository(sample):
    import fmcareer

    html = render(sample)
    foot = html[html.find("<footer>") : html.find("</footer>")]
    assert f"v{fmcareer.__version__}" in foot and "https://github.com/karl0ss/fmcareer" in foot
    assert "fmsave" not in foot and "Built entirely" not in html and "since retired" not in html


def chrome():
    """A headless Chromium to run the report in: FMCAREER_CHROME, PATH, or Playwright's cache."""
    if os.environ.get("FMCAREER_CHROME"):
        return os.environ["FMCAREER_CHROME"]
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome-headless-shell"):
        if shutil.which(name):
            return shutil.which(name)
    found = sorted(
        glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
    )
    return found[-1] if found else None


CHROME = chrome()
needs_chrome = pytest.mark.skipif(CHROME is None, reason="no headless Chromium found (set FMCAREER_CHROME)")


def dom(tmp_path, html, page):
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")
    out = subprocess.run(
        [
            CHROME,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--virtual-time-budget=3000",
            "--dump-dom",
            f"file://{path}#{page}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return out.stdout


def view_of(text):
    """The drawn page only: from the view up to the embedded data."""
    start = text.find('id="view"')
    return text[start : text.find('<script type="application/json"', start)]


PAGES = {
    "me": ["Alex Example", "2 clubs so far", "The climb", "Second Division Manager of the Season"],
    "seasons": ["2032/33", "First Division"],
    "season/2032-33": ["2032/33 season review", "Summary", "Out to Big City", "Where this season sits"],
    "season/2032-33/table": ["Final table", "Big City", "Not yet identified"],
    "season/2032-33/squad": ["Full squad statistics", "Old Retiree", "Partial", "Best XI"],
    "season/2031-32/transfers": ["Sam Striker", "Big City", "£1.50M"],
    "players": ["Sam Striker", "Gary Keeper"],
    "player/p202": ["Sam Striker", "Season by season", "£1.50M"],
    "records": ["Most goals", "5–0", "All-time players"],
    "records/transfers": ["Biggest signings", "Sam Striker"],
    "honours": ["Every cup run", "National Cup"],
    "transfers": ["Every move", "Show:", "Sam Striker"],
    "club": ["Example Park", "−£250k", "Balanced 4-4-2", "League table"],
    "club/table": ["live table", "Big City", "Example Town"],
    "club/squad": ["Gary Keeper", "Regular starter", "First team", "Under-18s"],
    "club/squad/under-18s": ["Young Prospect", "Youngster"],
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
    nav = text[text.find('id="nav"') : text.find("</nav>")]
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


@needs_chrome
def test_seasons_run_oldest_to_newest(tmp_path, sample):
    view = view_of(dom(tmp_path, render(sample), "seasons"))
    assert view.find("2029/30") < view.find("2031/32") < view.find("2032/33")


AI_TEXT = {
    "model": "test-model",
    "career": {"headline": "Example manager's rise", "paragraphs": ["An invented-for-tests feature."]},
    "seasons": {"2032/33": {"headline": "Town hold on", "paragraphs": ["A model-written report.", "Second."]}},
}


@needs_chrome
def test_report_opens_with_the_career_and_a_timeline_of_seasons(tmp_path, sample):
    sample["ai"] = AI_TEXT
    view = view_of(dom(tmp_path, render(sample), "report"))
    assert "An invented-for-tests feature." in view and "Written by test-model" in view
    assert "Town hold on" in view  # the model's headline on the timeline
    assert "Example Town crowned Second Division champions" in view  # the report's own where the model wrote none
    assert view.find("An invented-for-tests") < view.find("2029/30 · Old Rovers") < view.find("2032/33 · Example Town")
    assert 'href="#report/2029-30"' in view


@needs_chrome
def test_each_season_has_its_own_report_page_read_in_order(tmp_path, sample):
    sample["ai"] = AI_TEXT
    view = view_of(dom(tmp_path, render(sample), "report/2032-33"))
    assert "Town hold on" in view and "A model-written report." in view and "Second." in view
    assert 'href="#report/2031-32"' in view and "Full 2032/33 season review" in view
    first = view_of(dom(tmp_path, render(sample), "report/2029-30"))
    assert "← The career" in first and 'href="#report/2031-32"' in first


@needs_chrome
def test_season_summary_opens_with_the_article_and_the_overview_keeps_its_own_text(tmp_path, sample):
    sample["ai"] = AI_TEXT
    season = view_of(dom(tmp_path, render(sample), "season/2032-33"))
    assert "Town hold on" in season and "A model-written report." in season and "The numbers" in season
    me = view_of(dom(tmp_path, render(sample), "me"))
    assert "An invented-for-tests feature." not in me and "2 clubs so far" in me


@needs_chrome
def test_without_a_model_the_report_writes_its_own_articles(tmp_path, sample):
    view = re.sub(r"</?a[^>]*>", "", view_of(dom(tmp_path, render(sample), "report")))  # the text, links aside
    assert "Alex Example: 3 seasons, 1 promotion and 1 title" in view
    assert "Promotion came in 2031/32 (Second Division)." in view
    assert "Written by" not in view and "Example Town finish 12th in the First Division" in view
    season = view_of(dom(tmp_path, render(sample), "report/2032-33"))
    assert "12th-placed finish" in season


@needs_chrome
def test_header_and_overview_show_the_managers_face_else_the_club_badge(tmp_path, sample):
    text = dom(tmp_path, render(sample), "me")
    head = text[text.find('id="brand"') : text.find("</div>", text.find('id="brand"'))]
    assert "crest" in head and "data:image" not in head  # no face: the club's badge (initials)
    sample["images"] = {"person:101": "data:image/png;base64,AAAA"}
    text = dom(tmp_path, render(sample), "me")
    head = text[text.find('id="brand"') : text.find("</div>", text.find('id="brand"'))]
    assert 'class="pic face' in head and "crest" not in head
    assert view_of(text).count("data:image/png;base64,AAAA") >= 1  # the overview's big picture too


def test_pages_are_whole_documents_with_nothing_left_to_fill(sample):
    import re

    from fmcareer import web

    sample["manager"]["name"] = "Alex __FOOTER__ Example"  # data is filled last, so it is left alone
    for text in (render(sample), web.page("app", VERSION="1", FOOTER="f")):
        assert text.count("<style>") == 1 and "<script src" not in text
        assert not re.search(
            r"__(STYLE|SCRIPT|TITLE|FOOTER|DATA|VERSION)__", text.replace("Alex __FOOTER__ Example", "")
        )


def test_front_end_files_are_committed():
    """Every page file must be in git (an ignore rule once kept the HTML shells out)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        pytest.skip("not a git checkout")
    tracked = subprocess.run(["git", "ls-files", "fmcareer/web"], cwd=root, capture_output=True, text=True).stdout
    for name in ("report.html", "report.css", "report.js", "app.html", "app.css", "app.js"):
        assert f"fmcareer/web/{name}" in tracked, f"{name} is not committed"


@needs_chrome
def test_tabs_show_one_section_at_a_time(tmp_path, sample):
    summary = view_of(dom(tmp_path, render(sample), "season/2032-33"))
    assert "Full squad statistics" not in summary and "Not yet identified" not in summary
    squad = view_of(dom(tmp_path, render(sample), "season/2032-33/squad"))
    assert "Where this season sits" not in squad and 'class="on" aria-current="page">Squad' in squad
    # the pager keeps the tab when moving between seasons
    assert 'href="#season/2031-32/squad"' in squad


@needs_chrome
def test_transfers_fold_by_season_newest_open(tmp_path, sample):
    view = view_of(dom(tmp_path, render(sample), "transfers"))
    folds = re.findall(r'<details class="card fold"( open(?:="")?)?><summary><b>([^<]+)</b>', view)
    assert folds[0][1] == "2033/34" and folds[0][0] and all(not o for o, _ in folds[1:]) and len(folds) == 2


@needs_chrome
def test_long_tables_scroll_in_their_own_box(tmp_path, sample):
    short = view_of(dom(tmp_path, render(sample), "season/2032-33/squad"))
    assert "scroll tall" not in short
    row = sample["squad_stats"]["2032/33"][0]
    sample["squad_stats"]["2032/33"] = [dict(row, name=f"Player {i}", person_id=None) for i in range(20)]
    long = view_of(dom(tmp_path, render(sample), "season/2032-33/squad"))
    assert 'class="card scroll tall"' in long


@needs_chrome
def test_squad_is_split_by_team(tmp_path, sample):
    first = view_of(dom(tmp_path, render(sample), "club/squad"))
    assert "Gary Keeper" in first and "Young Prospect" not in first
    youth = view_of(dom(tmp_path, render(sample), "club/squad/under-18s"))
    assert "Young Prospect" in youth and "Gary Keeper" not in youth


@needs_chrome
def test_names_and_seasons_in_articles_click_through(tmp_path, sample):
    sample["ai"] = AI_TEXT
    sample["ai"]["seasons"]["2032/33"]["paragraphs"] = ["Sam Striker scored again, as in 2031/32."]
    view = view_of(dom(tmp_path, render(sample), "report/2032-33"))
    assert '<a href="#player/p202">Sam Striker</a>' in view and '<a href="#season/2031-32">2031/32</a>' in view
    squad = view_of(dom(tmp_path, render(sample), "club/squad"))
    assert '<a href="#player/p201">Gary Keeper</a>' in squad


def test_the_chosen_theme_is_set_before_the_page_draws(sample):
    from fmcareer.render import THEMES

    assert '<html lang="en" data-theme="fm26">' in render(sample)  # the default
    for theme in THEMES:
        sample["options"]["theme"] = theme
        assert f'data-theme="{theme}"' in render(sample)
    sample["options"]["theme"] = "<script>"  # anything else falls back to the default
    assert '<html lang="en" data-theme="fm26">' in render(sample)


def test_every_theme_has_its_styles():
    from fmcareer import web
    from fmcareer.render import THEMES

    css = web.read("report.css")
    assert all(f':root[data-theme="{t}"]' in css for t in THEMES if t != "fm26")
