"""The report's and the app's front end: one HTML shell, stylesheet and script each.

`page()` puts a page together as a single self-contained document (styles and script
inlined), which is what a report has to be to open anywhere on its own.
"""

from importlib.resources import files


def read(name: str) -> str:
    return (files(__name__) / name).read_text(encoding="utf-8")


def page(name: str, **values: str) -> str:
    """`<name>.html` with `<name>.css` and `<name>.js` inlined, then each `__KEY__` in it
    replaced by `values[KEY]`, in the order given (put untrusted data last)."""
    text = read(f"{name}.html").replace("__STYLE__", read(f"{name}.css")).replace("__SCRIPT__", read(f"{name}.js"))
    for key, value in values.items():
        text = text.replace(f"__{key}__", value)
    return text
