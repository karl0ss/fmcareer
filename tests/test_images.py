"""Reading the install's image catalog, and which images a career needs."""

import struct

from fmcareer.images import catalog, wanted_images


def entry(address, digest):
    """One catalog record: [u32 length] address [u32 32] 32 hex digits."""
    return struct.pack("<I", len(address)) + address + struct.pack("<I", 32) + digest


def test_catalog_reads_club_person_and_comp_addresses(tmp_path):
    core = tmp_path / "fm_Data" / "StreamingAssets" / "LicensedData" / "Core"
    core.mkdir(parents=True)
    data = (b"junk" + entry(b"club_715", b"04e94dcf3a706ce0969772fa363f48ed")
            + entry(b"person_28096339", b"04e807c3b44039b4ade796b45137d361")
            + entry(b"comp_13", b"a" * 32)
            + entry(b"balls2d_102430_1", b"b" * 32)       # a kind fmcareer does not use
            + entry(b"nation_flag_139", b"c" * 32))       # flags are not read yet
    (core / "catalog_info.bin").write_bytes(data)
    found = catalog(str(tmp_path))
    assert found == {
        ("club", 715): (str(core), "04e94dcf3a706ce0969772fa363f48ed"),
        ("person", 28096339): (str(core), "04e807c3b44039b4ade796b45137d361"),
        ("comp", 13): (str(core), "a" * 32),
    }


def test_catalog_of_a_folder_without_one_is_empty(tmp_path):
    assert catalog(str(tmp_path)) == {}


def test_wanted_images_cover_every_page(sample):
    want = wanted_images(sample)
    assert {("club", 10), ("club", 20), ("club", 30)} <= want          # stints, tables, transfers, live table
    assert {("person", 101), ("person", 201), ("person", 202), ("person", 203)} <= want
    assert {("comp", 901), ("comp", 902), ("comp", 905)} <= want
    assert not any(kind == "nation_flag" for kind, _ in want)
    assert ("person", None) not in want
