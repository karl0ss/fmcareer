"""fmcareer-names: which database versions it reads, and reading the game's database files."""

import struct
import sys

import pytest

from fmcareer.gamedb import parse_names, read_sections
from fmcareer.names import current_versions, main

if sys.version_info >= (3, 14):
    from compression import zstd
else:
    from backports import zstd


def test_reads_only_the_newest_games_databases():
    folders = ["2300", "2310", "2400", "2430", "2600", "2620", "notes"]
    assert current_versions(folders) == ["2600", "2620"]
    assert current_versions(["2400", "2430"]) == ["2400", "2430"]
    assert current_versions([]) == []


def container(wrapper, sections):
    """A made-up game database file: wrapper, header, zstd sections, zstd directory."""
    body, entries = b"", b""
    for name, ext, raw in sections:
        frame = zstd.compress(raw)
        entries += struct.pack("<I", len(name)) + name.encode() + struct.pack("<I", 4) + ext.encode()
        entries += struct.pack("<5Q", len(body), len(frame), len(raw), 0, 0)
        body += frame
    directory = struct.pack("<I", 4) + b"Test" + struct.pack("<I", 0) + entries
    header = b"\x02\x01fmf." + b"\x00" * 3 + struct.pack("<Q", 26 + len(body) - 9) + b"\x00" * 9
    return wrapper + header + body + b"\x02\x01fmf." + b"\x00" * 3 + zstd.compress(directory)


@pytest.mark.parametrize(
    "wrapper",
    [
        b"\x03\x01tad.\xb2\x0d",  # 8 bytes, older versions
        b"\x03\x01tad.\xa0\x0f\x8d\x0e\x07\x00",  # 12 bytes, newer
    ],
)
def test_sections_are_read_from_either_wrapper(tmp_path, wrapper):
    path = tmp_path / "lang_db.dat"
    sections = [("8_25", ".dat", b"english"), ("1_25", ".dat", b"other"), ("8_0", ".cmt", b"not a table")]
    path.write_bytes(container(wrapper, sections))
    assert read_sections(str(path), {"8_25", "8_0", "9_9"}) == {"8_25": b"english"}


def test_other_files_are_refused(tmp_path):
    path = tmp_path / "x.dat"
    path.write_bytes(b"not a game database at all")
    with pytest.raises(ValueError, match="not a Football Manager database"):
        read_sections(str(path), {"8_25"})


def test_name_tables_parse():
    def text(s):
        raw = s.encode()
        return struct.pack("<I", len(raw)) + raw

    table = b"\x03\x01tad." + b"\x00\x00" + struct.pack("<I", 2)
    table += struct.pack("<I", 7) + text("Example League") + b"\x00"
    table += struct.pack("<I", 9) + text("Example Cup") + b"\x01" + text("Cup") + b"\x00"
    assert parse_names(table) == {7: ["Example League"], 9: ["Example Cup", "Cup"]}


def test_wrong_folder_says_where_the_install_is(tmp_path):
    with pytest.raises(SystemExit, match="does not look like the Football Manager 26 install"):
        main([str(tmp_path), str(tmp_path / "names")])
