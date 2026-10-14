"""Where an FM26 install keeps the files fmcareer reads, on Windows, Linux and macOS.

On Windows they sit in the install folder (`shared/data/database/db`, `fm_Data/StreamingAssets`).
On macOS they are inside the app bundle: the database under
`fm.app/Contents/PlugIns/game_plugin.bundle/Contents/Resources/shared`, the Unity assets under
`fm.app/Contents/Resources/Data/StreamingAssets`. People pick the install folder, `fm.app`, or a
folder inside either, so each of those is tried, from the folder given and from its parents.
"""

import os
from pathlib import Path

_PLUGIN = ("PlugIns", "game_plugin.bundle", "Contents", "Resources")
DB_PLACES = [(), ("fm.app", "Contents", *_PLUGIN), ("Contents", *_PLUGIN), _PLUGIN]
ASSET_PLACES = [("fm_Data",), ("fm.app", "Contents", "Resources", "Data"), ("Contents", "Resources", "Data"), ("Data",)]
_UP = 9  # how many parents to try: enough to climb out of the deepest folder inside the bundle


def clean_path(text: str) -> str:
    """A folder as typed or pasted: no surrounding quotes, `~` expanded, and on macOS and Linux
    the backslash-escaped spaces a path copied from Terminal has."""
    text = text.strip().strip("\"'").strip()
    if os.sep == "/":
        text = text.replace("\\ ", " ")
    return os.path.expanduser(text) if text else ""


def _find(install: str, places: list[tuple[str, ...]], leaf: tuple[str, ...]) -> str | None:
    if not install:
        return None
    start = Path(clean_path(install))
    for base in [start, *list(start.parents)[:_UP]]:
        for place in places:
            if (found := base.joinpath(*place, *leaf)).is_dir():
                return str(found)
    return None


def database_dir(install: str) -> str | None:
    """The game database's `db` folder (one subfolder per database version), or None."""
    return _find(install, DB_PLACES, ("shared", "data", "database", "db"))


def licensed_data_dir(install: str) -> str | None:
    """The folder of licensed artwork bundles (`Core`, `Extra`), or None."""
    return _find(install, ASSET_PLACES, ("StreamingAssets", "LicensedData"))


def looks_like_saves(folder: str) -> bool:
    """Whether a folder is the game's user folder (saves, graphics) rather than its install."""
    p = Path(clean_path(folder))
    try:
        return any(x.suffix == ".fm" for x in p.iterdir()) or (p / "games").is_dir() or (p / "graphics").is_dir()
    except OSError:
        return False
