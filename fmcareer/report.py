"""Career history report for a manager, as a tabbed HTML page.

Usage: fmcareer SAVE "Manager Name" NAMES_DIR [-o report.html] [--json data.json]

NAMES_DIR holds competition_names.csv / award_names.csv from fmcareer-names.
Everything shown is decoded from the save (fmcareer.collect) and rendered by
fmcareer.render into one self-contained file.
"""
import argparse
import json
import time

from fmcareer.collect import collect
from fmcareer.render import render


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save"); ap.add_argument("manager"); ap.add_argument("names")
    ap.add_argument("-o", "--out", default="career_report.html")
    ap.add_argument("--json", help="also write the collected data as JSON")
    ap.add_argument("--install", help="FM26 install folder: embed club badges, player photos, "
                    "competition logos and flags from it (needs UnityPy)")
    a = ap.parse_args()
    t = time.time()
    data = collect(a.save, a.manager, a.names)
    if a.install:
        from fmcareer.images import load, wanted_images
        data["images"] = load(a.install, wanted_images(data))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    m = data["manager"]
    clubs = ", ".join(st["club"] for st in data["stints"])
    print(f"{m['name']} ({clubs}): {len(data['league'])} seasons, {len(data['honours'])} trophies, "
          f"{len(data['awards'])} awards, {len(data['best_eleven'])} best XIs, {len(data['transfers'])} moves "
          f"-> {a.out} ({time.time() - t:.0f}s)")


if __name__ == "__main__":
    main()
