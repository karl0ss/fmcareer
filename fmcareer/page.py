"""A finished career's report page: the page put together, its placeholders filled from the data.

fm-careers, the site that hosts reports, rebuilds each one from its stored data with these, so a
hosted report is the file fmcareer makes. Keep this module free of fmsave and the save decoders:
the site installs fmcareer without them.
"""

import html
import json
import re

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


def assemble(page: str, css: str, js: str) -> str:
    """A page's HTML with its stylesheet and script inlined; its other placeholders are left in."""
    return page.replace("__STYLE__", css).replace("__SCRIPT__", js)


def fill(page: str, values: dict[str, str]) -> str:
    """Each `__KEY__` in an assembled page replaced by `values[KEY]`, in the order given (put
    untrusted data last)."""
    for key, value in values.items():
        page = page.replace(f"__{key}__", value)
    return page


def footer(version: str) -> str:
    """fmcareer's version, linked to its site (downloads and an example report)."""
    return f'<a href="https://karl0ss.github.io/fmcareer/">fmcareer</a> v{html.escape(version)}'


def report(shell: str, data: Record, version: str) -> str:
    """The report for a career: the assembled report page (`shell`) filled in, the data last."""
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{data['manager']['name']}: career history")
    theme = (data.get("options") or {}).get("theme")
    return fill(
        shell,
        {"THEME": theme if theme in THEMES else "fm26", "TITLE": title, "FOOTER": footer(version), "DATA": payload},
    )


def no_em_dashes(text: str) -> str:
    """The report has no em dashes, whatever a model writes: each becomes a comma."""
    return re.sub(r"\s*—\s*", ", ", text)
