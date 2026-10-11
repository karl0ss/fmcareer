"""Render collect() output as one self-contained, multi-page HTML report.

The page itself is fmcareer/web/report.{html,css,js}; the career goes in as JSON and the
script draws the pages (hash-routed: #me, #seasons, #season/<yyyy-yy>, #players,
#player/<id>, #records, #honours, #transfers, #club).
"""

import html
import json

from fmcareer import web
from fmcareer._types import Record


def footer() -> str:
    """fmcareer's version, linked to its repository."""
    from fmcareer import __version__

    return f'<a href="https://github.com/karl0ss/fmcareer">fmcareer</a> v{html.escape(__version__)}'


def render(data: Record) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{data['manager']['name']} — Career History")
    return web.page("report", TITLE=title, FOOTER=footer(), DATA=payload)
