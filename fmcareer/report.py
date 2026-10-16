"""Career history report for a manager, as a tabbed HTML page.

Usage: fmcareer SAVE "Manager Name" NAMES_DIR [-o report.html] [--json data.json]

NAMES_DIR holds competition_names.csv / award_names.csv from fmcareer-names.
Everything shown is decoded from the save (fmcareer.collect) and rendered by
fmcareer.render into one self-contained file.
"""

import argparse
import json
import time

from fmcareer.collect import collect, report_gaps
from fmcareer.render import THEMES, render

SHOW_WORDS = {"Loan": "loans", "Trial": "trials", "Youth intake": "youth", "Released": "released", "staff": "staff"}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("save")
    ap.add_argument("manager")
    ap.add_argument("names")
    ap.add_argument("-o", "--out", default="career_report.html")
    ap.add_argument("--json", help="also write the collected data as JSON")
    ap.add_argument(
        "--sections",
        help="pages to include, comma-separated, from: "
        "me,seasons,players,records,honours,transfers,club (default: all)",
    )
    ap.add_argument(
        "--show",
        help="move types transfer lists show at first, comma-separated, from: "
        "loans,trials,youth,released,staff (default: released)",
    )
    ap.add_argument("--theme", choices=sorted(THEMES), help="the report's colour theme (default: fm26)")
    ap.add_argument(
        "--install",
        help="FM26 install folder: embed club badges, player photos, "
        "competition logos and flags from it (needs UnityPy)",
    )
    ap.add_argument(
        "--graphics",
        help="the game's graphics folder: logo and face packs there win over "
        "the install's images (needs Pillow, part of the images extra)",
    )
    a = ap.parse_args()
    t = time.time()
    options = {}
    if a.theme:
        options["theme"] = a.theme
    if a.sections:
        options["sections"] = [x.strip() for x in a.sections.split(",") if x.strip()]
    if a.show is not None:
        picked = {x.strip() for x in a.show.split(",")}
        options["show"] = {key: word in picked for key, word in SHOW_WORDS.items()}
    data = collect(a.save, a.manager, a.names, options=options)
    if a.install or a.graphics:
        from fmcareer.images import by_report_key, load, load_pack, picture_keys

        keys = picture_keys(data)
        want = {filed for filed, _shown in keys}
        pack = load_pack(a.graphics, want) if a.graphics else {}
        game = load(a.install, {k for k in want if f"{k[0]}:{k[1]}" not in pack}) if a.install else {}
        data["images"] = by_report_key({**game, **pack}, keys)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    m = data["manager"]
    clubs = ", ".join(st["club"] for st in data["stints"])
    print(
        f"{m['name']} ({clubs}): {len(data['league'])} seasons, {len(data['honours'])} trophies, "
        f"{len(data['awards'])} awards, {len(data['best_eleven'])} best XIs, {len(data['transfers'])} moves "
        f"-> {a.out} ({time.time() - t:.0f}s)"
    )
    for g in report_gaps(data):
        print(f"Missing: {g['count']} {g['kind']} without a name, e.g. {', '.join(g['examples'])}")
    for p in data.get("problems", []):
        print(f"Missing: {p['part']} left out ({p['error']})")


if __name__ == "__main__":
    main()
