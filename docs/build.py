"""Build the GitHub Pages site into _site/: the landing page and an example report.

The example is the tests' made-up career (`SAMPLE` in tests/conftest.py) rendered by this
fmcareer, so the site always shows what the current version makes.

Usage: python docs/build.py [OUT_DIR]   (default: _site)
"""

import copy
import importlib.util
import shutil
import sys
from pathlib import Path

from fmcareer import __version__
from fmcareer.render import render

ROOT = Path(__file__).resolve().parent.parent


def sample() -> dict:
    spec = importlib.util.spec_from_file_location("conftest", ROOT / "tests" / "conftest.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return copy.deepcopy(module.SAMPLE)


def build(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(page.replace("__VERSION__", __version__), encoding="utf-8")
    shutil.copy(ROOT / "docs" / "site.css", out)
    shutil.copy(ROOT / "fmcareer" / "web" / "logo.svg", out)
    (out / "example.html").write_text(render(sample()), encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site"))
