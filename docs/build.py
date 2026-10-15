"""Build the GitHub Pages site into _site/: the landing page and an example report.

The example is a real career, Karl0ss at St. Albans City, shared by its manager: its data
(docs/example.json.gz, as fm-careers.co.uk stores it) rendered by this fmcareer, so the site
always shows the current report page. It's one file; the page's theme switcher changes the
theme inside the frame, as the report's themes are only its <html data-theme>.

Usage: python docs/build.py [OUT_DIR]   (default: _site)
"""

import gzip
import json
import shutil
import sys
from html import escape
from pathlib import Path

from fmcareer import __version__
from fmcareer.render import THEMES, render

ROOT = Path(__file__).resolve().parent.parent


def example() -> dict:
    return json.loads(gzip.decompress((ROOT / "docs" / "example.json.gz").read_bytes()))


def build(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    data = example()
    theme = (data.get("options") or {}).get("theme")
    theme = theme if theme in THEMES else "fm26"
    page = page.replace("__THEMES__", theme_buttons(theme)).replace("__VERSION__", __version__)
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.copy(ROOT / "docs" / "site.css", out)
    shutil.copy(ROOT / "fmcareer" / "web" / "logo.svg", out)
    (out / "example.html").write_text(render(data), encoding="utf-8")


def theme_buttons(current: str) -> str:
    """The switcher: a button per theme, the example's own theme pressed."""
    return "".join(
        f'<button type="button" data-theme="{theme}" aria-pressed="{"true" if theme == current else "false"}">'
        f'<i style="background:{page}"><b style="background:{accent}"></b></i>{escape(name)}</button>'
        for theme, (name, (page, _card, accent)) in THEMES.items()
    )


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site"))
