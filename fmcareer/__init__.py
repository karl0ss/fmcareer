"""fmcareer: a manager's career history report from a Football Manager 26 save.

Built on fmsave (https://github.com/karl0ss/fmsave, branch history-decoders),
which decodes the save; fmcareer joins the decoded tables into one career and
renders it as a self-contained HTML page.
"""

__version__ = "0.0.11"

from fmcareer.collect import collect
from fmcareer.render import render

__all__ = ["__version__", "collect", "render"]
