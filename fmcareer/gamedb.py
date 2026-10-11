"""Parse FM26 game-database language name tables (scratch; outside the fmsave package).

Table layout (`tad.`): u32 count, then per record [u32 database id] and strings
`[u32 len][utf-8]`, each followed by a flag byte. Competition tables (25) end a
record with flag 00; award tables (0) carry flags ff/01 and one trailing byte 00.
"""
import struct
from fmsave._container import read_index
from fmsave._save import read_section


def _parse(b, trailing):
    count = struct.unpack_from('<I', b, 8)[0]; o = 12; out = {}
    for _ in range(count):
        rid = struct.unpack_from('<I', b, o)[0]; o += 4; strs = []
        while True:
            n = struct.unpack_from('<I', b, o)[0]; o += 4
            strs.append(b[o:o + n].decode('utf-8', 'replace')); o += n
            flag = b[o]; o += 1
            if not trailing and flag == 0:
                break
            if trailing and b[o] == 0:
                o += 1; break
        out[rid] = strs
    return out, o


def parse_names(b):
    assert b[:6] == b'\x03\x01tad.'
    for trailing in (False, True):
        try:
            out, end = _parse(b, trailing)
        except (IndexError, struct.error):
            continue
        if end == len(b):
            return out
    raise ValueError('table did not parse exactly')


def english_names(db_paths, table):
    """Merge English (language 8) names for one table, later databases overriding."""
    names = {}
    for path in db_paths:
        ix = read_index(path)
        if f'8_{table}' in ix.sections:
            names.update(parse_names(read_section(ix, f'8_{table}')))
    return names
