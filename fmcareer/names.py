"""Extract English competition and award names from an FM26 install.

Usage: fmcareer-names FM26_INSTALL_DIR OUT_DIR [--db 2600 --db 2620 ...]  (default: the newest game's versions)

Kept outside the fmsave package on purpose: fmsave ships no names and reads no
game install; it accepts a user-built `database_id,name` CSV via
`fmsave.open(save, competition_names=...)`. This script builds that CSV (and an
award-name CSV for the career report) from the game's own database files.

Game database files (`shared/data/database/db/<ver>/<ver>_fm/*.dat`) are a short
`03 01 'tad.'` wrapper (8 bytes in older database versions, 12 in newer ones)
around the same `fmf.` container a save uses.
`lang_db.dat` / `lang_update_db.dat` hold per-language name tables named
`<language>_<table>`; language 8 is English. Table 25 = competitions keyed on
the editor database id (the save's `Competition.database_id`); table 0 =
awards, and a save's `Award.award_id` is the row's position in that table
(ordered by database id).
"""
import argparse
import csv
import os
import sys
import tempfile

from fmcareer.gamedb import english_names

CONTAINER = b'\x02\x01fmf.'


def unwrap(src, tmpdir):
    """Copy a game .dat without its wrapper so fmsave's container reader opens it."""
    dst = os.path.join(tmpdir, os.path.basename(os.path.dirname(src)) + '_' + os.path.basename(src) + '.fm')
    with open(src, 'rb') as f, open(dst, 'wb') as g:
        head = f.read(64)
        start = head.find(CONTAINER)
        if head[:6] != b'\x03\x01tad.' or start < 0:
            raise SystemExit(f'{src}: unexpected header')
        f.seek(start)
        while chunk := f.read(1 << 20):
            g.write(chunk)
    return dst


def current_versions(folders):
    """The newest game's database versions, ascending (2600, 2620 for FM26).

    Installs also carry older games' databases (23xx in an older container format, 24xx);
    FM26 saves refer to their own, and merging older award tables would shift award indexes.
    """
    versions = sorted(v for v in folders if v.isdigit() and len(v) == 4)
    if not versions:
        return []
    newest = versions[-1][:2]
    return [v for v in versions if v[:2] == newest]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--db', action='append', help="database versions in load order (default: the newest game's, ascending)")
    a = ap.parse_args(argv)
    root = os.path.join(a.install, 'shared', 'data', 'database', 'db')
    if not os.path.isdir(root):
        raise SystemExit(f'{a.install} does not look like the Football Manager 26 install folder '
                         f'(no shared/data/database/db inside). With Steam it is usually '
                         r'C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26')
    versions = a.db or current_versions(os.listdir(root))
    os.makedirs(a.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for ver in versions:
            for fn in ('lang_db.dat', 'lang_update_db.dat'):
                p = os.path.join(root, ver, f'{ver}_fm', fn)
                if os.path.exists(p):
                    paths.append(unwrap(p, tmp))
        comps = english_names(paths, 25)
        awards = english_names(paths, 0)
    with open(os.path.join(a.out, 'competition_names.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for db_id in sorted(comps):
            w.writerow([db_id, comps[db_id][0]])
    with open(os.path.join(a.out, 'award_names.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['award_index', 'database_id', 'name'])
        for index, db_id in enumerate(sorted(awards)):
            w.writerow([index, db_id, awards[db_id][0]])
    print(f'{len(comps)} competitions, {len(awards)} awards from {len(paths)} files -> {a.out}')


if __name__ == '__main__':
    main(sys.argv[1:])
