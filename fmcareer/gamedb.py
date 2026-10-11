"""Parse FM26 game-database language name tables (used by fmcareer-names).

Table layout (`tad.`): u32 count, then per record [u32 database id] and strings
`[u32 len][utf-8]`, each followed by a flag byte. Competition tables (25) end a
record with flag 00; award tables (0) carry flags ff/01 and one trailing byte 00.

The tables sit in the same container format a save uses, which fmsave reads; it has no
public function for raw sections (its public API reads saves, and a game database file is
not one), so its two private readers are used here, in this one place only.
"""

import struct

try:
    from fmsave._container import read_index
    from fmsave._save import read_section
except ImportError as error:  # fmsave reorganised its internals
    read_index = read_section = None
    _IMPORT_ERROR = error
else:
    _IMPORT_ERROR = None


def _parse(b, trailing):
    count = struct.unpack_from("<I", b, 8)[0]
    o, out = 12, {}
    for _ in range(count):
        rid = struct.unpack_from("<I", b, o)[0]
        o += 4
        strs = []
        while True:
            n = struct.unpack_from("<I", b, o)[0]
            o += 4
            strs.append(b[o : o + n].decode("utf-8", "replace"))
            o += n
            flag = b[o]
            o += 1
            if not trailing and flag == 0:
                break
            if trailing and b[o] == 0:
                o += 1
                break
        out[rid] = strs
    return out, o


def parse_names(b):
    """{database id: [names]} from one language table, which must parse to its last byte."""
    if b[:6] != b"\x03\x01tad.":
        raise ValueError("not a name table")
    for trailing in (False, True):
        try:
            out, end = _parse(b, trailing)
        except (IndexError, struct.error):
            continue
        if end == len(b):
            return out
    raise ValueError("table did not parse exactly")


def english_names(db_paths, table):
    """Merge English (language 8) names for one table, later databases overriding."""
    if _IMPORT_ERROR is not None:
        raise SystemExit(
            f"this fmsave version moved the container readers fmcareer-names uses ({_IMPORT_ERROR}); update fmcareer"
        ) from _IMPORT_ERROR
    names = {}
    for path in db_paths:
        ix = read_index(path)
        if f"8_{table}" in ix.sections:
            names.update(parse_names(read_section(ix, f"8_{table}")))
    return names
