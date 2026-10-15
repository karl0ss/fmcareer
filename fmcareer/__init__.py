"""fmcareer: a manager's career history report from a Football Manager 26 save.

Built on fmsave (https://github.com/karl0ss/fmsave, branch history-decoders),
which decodes the save; fmcareer joins the decoded tables into one career and
renders it as a self-contained HTML page.
"""

__version__ = "0.0.24"

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fmcareer.collect import collect
    from fmcareer.render import render

__all__ = ["__version__", "collect", "render"]


def __getattr__(name: str):
    # loaded on first use, not here: fm-careers imports fmcareer.page and fmcareer.league without
    # fmsave installed, and importing those runs this file
    if name == "collect":
        from fmcareer.collect import collect

        return collect
    if name == "render":
        from fmcareer.render import render

        return render
    raise AttributeError(f"module 'fmcareer' has no attribute {name!r}")
