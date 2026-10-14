"""Render collect() output as one self-contained, multi-page HTML report.

The page itself is fmcareer/web/report.{html,css,js}; the career goes in as JSON and the
script draws the pages (hash-routed: #me, #seasons, #season/<yyyy-yy>, #players,
#player/<id>, #records, #honours, #transfers, #club).
"""

import html
import json

from fmcareer import web
from fmcareer._types import Record

# the report's colour themes (fmcareer/web/report.css): id -> (name, swatch: page, card, accent)
THEMES = {
    "fm26": ("FM26", ("#0c0d24", "#171936", "#c77dff")),
    "midnight": ("Midnight", ("#07111f", "#0f1e33", "#5cc8ff")),
    "pitch": ("Pitch", ("#07150e", "#0e2318", "#8ee67c")),
    "crimson": ("Crimson", ("#120b0d", "#1e1416", "#ff7a7a")),
    "club": ("Club colours", ("#0e0f14", "#181a22", "linear-gradient(90deg, #6b4bd6, #e0b04f)")),
    "light": ("Matchday light", ("#f4f5fa", "#ffffff", "#5b2fd6")),
}


def footer() -> str:
    """fmcareer's version, linked to its repository."""
    from fmcareer import __version__

    return f'<a href="https://github.com/karl0ss/fmcareer">fmcareer</a> v{html.escape(__version__)}'


def render(data: Record) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{data['manager']['name']}: career history")
    theme = (data.get("options") or {}).get("theme")
    return web.page("report", THEME=theme if theme in THEMES else "fm26", TITLE=title, FOOTER=footer(), DATA=payload)
