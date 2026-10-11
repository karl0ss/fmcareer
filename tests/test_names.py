"""fmcareer-names: which database versions it reads, and unwrapping game files."""

import pytest

from fmcareer.names import CONTAINER, current_versions, main, unwrap


def test_reads_only_the_newest_games_databases():
    folders = ["2300", "2310", "2400", "2430", "2600", "2620", "notes"]
    assert current_versions(folders) == ["2600", "2620"]
    assert current_versions(["2400", "2430"]) == ["2400", "2430"]
    assert current_versions([]) == []


@pytest.mark.parametrize("wrapper", [b"\x03\x01tad.\xb2\x0d",                  # 8 bytes, older versions
                                     b"\x03\x01tad.\xa0\x0f\x8d\x0e\x07\x00"])  # 12 bytes, newer
def test_unwrap_strips_either_wrapper(tmp_path, wrapper):
    body = CONTAINER + b"rest of the container"
    src = tmp_path / "2600" / "lang_db.dat"
    src.parent.mkdir()
    src.write_bytes(wrapper + body)
    out = tmp_path / "out"
    out.mkdir()
    assert open(unwrap(str(src), str(out)), "rb").read() == body


def test_unwrap_rejects_other_files(tmp_path):
    src = tmp_path / "x.dat"
    src.write_bytes(b"not a game database at all")
    with pytest.raises(SystemExit, match="unexpected header"):
        unwrap(str(src), str(tmp_path))


def test_wrong_folder_says_where_the_install_is(tmp_path):
    with pytest.raises(SystemExit, match="does not look like the Football Manager 26 install"):
        main([str(tmp_path), str(tmp_path / "names")])
