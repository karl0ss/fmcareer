"""Render collect() output as one self-contained, multi-page HTML report.

The page itself is fmcareer/web/report.{html,css,js}; the career goes in as JSON and the
script draws the pages (hash-routed: #me, #seasons, #season/<yyyy-yy>, #players,
#player/<id>, #records, #honours, #transfers, #club).
"""

from fmcareer import page, web
from fmcareer._types import Record
from fmcareer.page import THEMES

__all__ = ["THEMES", "footer", "render"]


def footer() -> str:
    """fmcareer's version, linked to its site."""
    from fmcareer import __version__

    return page.footer(__version__)


def render(data: Record) -> str:
    from fmcareer import __version__

    return page.report(web.page("report"), data, __version__)
