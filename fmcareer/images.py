"""Club badges, player photos, competition logos and flags from the user's FM26 install.

The game ships its licensed artwork as Unity asset bundles under
`fm_Data/StreamingAssets/LicensedData/{Core,Extra}`. Each folder's `catalog_info.bin`
(an Addressables catalog) names every image by an address and the hash its bundle files
it under:

    [u32 length] "<kind>_<id>" [u32 32] "<32 hex digits>"

with kinds `club` (keyed by the save's club uid), `person` (keyed by the person's unique
id, the save's uid + 1) and `comp` (the competition's editor database id). Nation flags
(`nation_flag_<nation id>`) sit in sprite atlases under other keys and are not read yet.
The images are read from the user's own install at report time and
embedded in their report; nothing from the game is stored in this repository.

Needs the optional dependency UnityPy (`pip install fmcareer[images]`).
"""
import base64
import io
import os
import re

KINDS = {"club": "club-", "person": "players-", "comp": "comp-"}
_ADDRESS = re.compile(rb"([a-z_]+?)_(\d+)\x20\x00\x00\x00([0-9a-f]{32})")
_SIZE = {"club": 96, "person": 96, "comp": 64}


def _folders(install):
    root = os.path.join(install, "fm_Data", "StreamingAssets", "LicensedData")
    return [os.path.join(root, f) for f in ("Core", "Extra") if os.path.isdir(os.path.join(root, f))]


def catalog(install):
    """{(kind, id): (folder, hash)} for every image kind fmcareer uses."""
    found = {}
    for folder in _folders(install):
        path = os.path.join(folder, "catalog_info.bin")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            data = f.read()
        for kind, ident, digest in _ADDRESS.findall(data):
            kind = kind.decode()
            if kind in KINDS:
                found.setdefault((kind, int(ident)), (folder, digest.decode()))
    return found


def load(install, wanted):
    """Data URIs for the wanted (kind, id) pairs the install has: {"kind:id": uri}.

    Only the bundles of the wanted kinds are opened, and only matching textures are
    decoded; each is scaled down and stored as a PNG.
    """
    import UnityPy  # optional dependency

    index = catalog(install)
    by_hash = {}
    for key in wanted:
        hit = index.get(key)
        if hit:
            by_hash.setdefault(hit, key)
    out = {}
    if not by_hash:
        return out
    folders = {folder for folder, _digest in by_hash}
    kinds = {key[0] for key in by_hash.values()}
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".bundle") or not any(name.startswith(KINDS[k]) for k in kinds):
                continue
            env = UnityPy.load(os.path.join(folder, name))
            for path, obj in env.container.items():
                key = by_hash.get((folder, path))
                if key is None or obj.type.name != "Texture2D":
                    continue
                image = obj.read().image
                size = _SIZE[key[0]]
                image.thumbnail((size, size))
                buf = io.BytesIO()
                image.save(buf, format="PNG", optimize=True)
                out[f"{key[0]}:{key[1]}"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return out


def wanted_images(data):
    """Every (kind, id) a collected career can show."""
    want = set()
    for st in data.get("stints", []):
        want.add(("club", st["club_uid"]))
    for rows in data.get("tables", {}).values():
        want.update(("club", r["club_uid"]) for r in rows if r.get("club_uid") is not None)
    for m in data.get("transfers", []):
        if m.get("other_uid") is not None:
            want.add(("club", m["other_uid"]))
        if m.get("person_id") is not None:
            want.add(("person", m["person_id"]))
    for c in data.get("cups", []):
        if c.get("opponent_uid") is not None:
            want.add(("club", c["opponent_uid"]))
    for group in ("league", "cups", "honours"):
        want.update(("comp", r["competition_db"]) for r in data.get(group, []) if r.get("competition_db"))
    for rows in list(data.get("best_eleven", {}).values()) + list(data.get("squad_stats", {}).values()):
        want.update(("person", r["person_id"]) for r in rows if r.get("person_id") is not None)
    for p in data.get("squad", []):
        want.add(("person", p["person_id"]))
    m = data.get("manager", {})
    if m.get("person_id"):
        want.add(("person", m["person_id"]))
    today = data.get("club_today") or {}
    want.update(("person", p["person_id"]) for p in today.get("squad", []))
    live = today.get("live_table") or {}
    want.update(("club", r["club_uid"]) for r in live.get("rows", []) if r.get("club_uid") is not None)
    if live.get("competition_db"):
        want.add(("comp", live["competition_db"]))
    career = data.get("career") or {}
    for key in ("record_signing", "record_sale"):
        if career.get(key) and career[key].get("person_id"):
            want.add(("person", career[key]["person_id"]))
    return want
