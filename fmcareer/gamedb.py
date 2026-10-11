"""Read FM26 game-database name tables (used by fmcareer-names).

A game database file (`shared/data/database/db/<ver>/<ver>_fm/*.dat`) is a short
`03 01 'tad.'` wrapper (8 bytes in older database versions, 12 in newer ones) around a
container: a 26-byte header starting `02 01 'fmf.'` whose u64 at byte 9 (counted from
byte 9) points to a directory at the end of the file. The directory is one zstd frame:
a length-prefixed name, a u32, then per entry `[u32 n] name [u32 4] extension` and five
u64s (offset from byte 26, compressed size, size, two more). Each `.dat` entry is a zstd
frame holding one table.

Table layout (`tad.`): u32 count, then per record [u32 database id] and strings
`[u32 len][utf-8]`, each followed by a flag byte. Competition tables (25) end a
record with flag 00; award tables (0) carry flags ff/01 and one trailing byte 00.
Language tables are named `<language>_<table>`; language 8 is English.

fmcareer reads these files itself: fmsave reads saves only and never the game install.
"""

import struct
import sys

if sys.version_info >= (3, 14):
    from compression import zstd
else:
    from backports import zstd

WRAPPER = b"\x03\x01tad."
CONTAINER = b"\x02\x01fmf."
FRAME_BASE = 26
MAX_SECTION_BYTES = 512 * 1024 * 1024


def container_start(head: bytes) -> int:
    """Where the container begins inside a game database file's first bytes."""
    start = head.find(CONTAINER)
    if head[:6] != WRAPPER or start < 0:
        raise ValueError("not a Football Manager database file")
    return start


def read_sections(path: str, wanted: set[str]) -> dict[str, bytes]:
    """The `.dat` sections of a game database file whose names are in `wanted`."""
    with open(path, "rb") as f:
        base = container_start(f.read(64))
        f.seek(base)
        header = f.read(FRAME_BASE)
        directory_at = 9 + struct.unpack_from("<Q", header, 9)[0]
        f.seek(base + directory_at)
        trailer = f.read()
        if trailer[:6] != CONTAINER:
            raise ValueError(f"{path}: the directory is damaged")
        directory = zstd.decompress(trailer[9:])
        name_length = struct.unpack_from("<I", directory, 0)[0]
        cursor, found = 4 + name_length + 4, {}
        while cursor + 4 <= len(directory):
            n = struct.unpack_from("<I", directory, cursor)[0]
            if not 1 <= n <= 256 or cursor + 4 + n + 8 + 40 > len(directory):
                break
            name = directory[cursor + 4 : cursor + 4 + n].decode("ascii", "replace")
            ext_at = cursor + 4 + n
            extension = directory[ext_at + 4 : ext_at + 8].decode("ascii", "replace")
            offset, compressed, size, _a, _b = struct.unpack_from("<5Q", directory, ext_at + 8)
            cursor = ext_at + 8 + 40
            if extension == ".dat" and name in wanted:
                if size > MAX_SECTION_BYTES:
                    raise ValueError(f"{path}: section {name} is implausibly large")
                f.seek(base + FRAME_BASE + offset)
                found[name] = zstd.decompress(f.read(compressed))
    return found


def _parse(b: bytes, trailing: bool) -> tuple[dict[int, list[str]], int]:
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


def parse_names(b: bytes) -> dict[int, list[str]]:
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


def english_names(db_paths: list[str], table: int) -> dict[int, list[str]]:
    """Merge English (language 8) names for one table, later databases overriding."""
    names: dict[int, list[str]] = {}
    for path in db_paths:
        for raw in read_sections(path, {f"8_{table}"}).values():
            names.update(parse_names(raw))
    return names
