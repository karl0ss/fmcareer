"""A release's notes: its CHANGELOG.md section under "What's new", then how to install it.

Usage: python packaging/release_notes.py VERSION > notes.md  (the Release workflow's body)

The app reads the bullets under "What's new" from the latest release to say what a new version
brings, so that heading and its "- " bullets are part of the format.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

INSTALL = """## Download

**Windows:** download `fmcareer-*-windows.exe` and double-click it: the app opens in your browser.
Leave the black window open while you use it; close it to stop.
Windows may warn about an unrecognised app the first time (the exe isn't code-signed):
choose "More info" then "Run anyway".

**macOS (Apple silicon):** download `fmcareer-*-macos-arm64.tar.gz`, double-click it to unpack,
then in Terminal run `xattr -d com.apple.quarantine fmcareer` in that folder once (the program isn't signed),
and start it with `./fmcareer`. The app opens in your browser; leave Terminal open while you use it.

**Linux (x64):** download `fmcareer-*-linux-x64.tar.gz`, then `tar -xzf fmcareer-*-linux-x64.tar.gz && ./fmcareer`.
"""


def section(version: str, text: str | None = None) -> list[str]:
    """The changelog's bullets for a version, each joined onto one line."""
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    match = re.search(rf"^## {re.escape(version)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return []
    bullets: list[str] = []
    for line in match.group(1).splitlines():
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + line.strip()
    return bullets


def notes(version: str) -> str:
    bullets = section(version)
    if not bullets:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    return "## What's new\n\n" + "".join(f"- {b}\n" for b in bullets) + "\n" + INSTALL


if __name__ == "__main__":
    sys.stdout.write(notes(sys.argv[1]))
