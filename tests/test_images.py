"""Reading the install's image catalog, and which images a career needs."""

import struct

from fmcareer.images import catalog, wanted_images


def entry(address, digest):
    """One catalog record: [u32 length] address [u32 32] 32 hex digits."""
    return struct.pack("<I", len(address)) + address + struct.pack("<I", 32) + digest


def test_catalog_reads_club_person_and_comp_addresses(tmp_path):
    core = tmp_path / "fm_Data" / "StreamingAssets" / "LicensedData" / "Core"
    core.mkdir(parents=True)
    data = (
        b"junk"
        + entry(b"club_715", b"04e94dcf3a706ce0969772fa363f48ed")
        + entry(b"person_28096339", b"04e807c3b44039b4ade796b45137d361")
        + entry(b"comp_13", b"a" * 32)
        + entry(b"balls2d_102430_1", b"b" * 32)  # a kind fmcareer does not use
        + entry(b"nation_flag_139", b"c" * 32)
    )  # flags are not read yet
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
    assert {("club", 10), ("club", 20), ("club", 30)} <= want  # stints, tables, transfers, live table
    assert {("person", 101), ("person", 201), ("person", 202), ("person", 203)} <= want
    assert {("comp", 901), ("comp", 902), ("comp", 905)} <= want
    assert not any(kind == "nation_flag" for kind, _ in want)
    assert ("person", None) not in want


def png(path, colour):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (8, 8), colour).save(path)
    return path


def test_packs_by_file_name_and_by_config(tmp_path):
    from fmcareer.images import load_pack, pack_images

    g = tmp_path / "graphics"
    badge = png(g / "logos" / "Clubs" / "Normal" / "Normal" / "716.png", "blue")
    png(g / "logos" / "Clubs" / "Retro" / "Normal" / "716.png", "red")  # retro sets are skipped
    png(g / "logos" / "Clubs" / "Normal" / "Small" / "717.png", "red")  # so are small sizes
    comp = png(g / "logos" / "Competitions" / "Normal" / "Normal" / "901.png", "green")
    face = png(g / "faces" / "Big_Pack" / "12345.png", "white")
    png(g / "faces" / "Big_Pack" / "999.png", "white")  # not mapped, so not used
    (g / "faces" / "Big_Pack" / "config.xml").write_text(
        '<record><list id="maps"><record from="12345" to="graphics/pictures/person/12345/portrait"/></list></record>'
    )
    newgen = png(g / "faces" / "Generated" / "Caucasian" / "Caucasian7.png", "white")
    (g / "faces" / "Generated" / "nonfic.xml").write_text(
        '<list id="maps"><record from="Caucasian/Caucasian7" to="graphics/pictures/person/r-2000000001/portrait"/>'
        '<record from="Caucasian/Missing" to="graphics/pictures/person/r-2000000002/portrait"/></list>'
    )
    want = {
        ("club", 716),
        ("club", 717),
        ("comp", 901),
        ("person", 12345),
        ("person", 999),
        ("person", 2000000001),
        ("person", 2000000002),
        ("club", 1),
    }
    assert pack_images(str(g), want) == {
        ("club", 716): str(badge),
        ("comp", 901): str(comp),
        ("person", 12345): str(face),
        ("person", 2000000001): str(newgen),
    }
    pics = load_pack(str(g), want)
    assert set(pics) == {"club:716", "comp:901", "person:12345", "person:2000000001"}
    assert all(uri.startswith("data:image/png;base64,") for uri in pics.values())


def test_pack_logo_beats_a_small_icon_and_missing_folders_are_empty(tmp_path):
    from fmcareer.images import guess_graphics, pack_images

    g = tmp_path / "graphics"
    icon = png(g / "mine" / "icon716.png", "red")
    logo = png(g / "mine" / "logo716.png", "blue")
    (g / "mine" / "config.xml").write_text(
        '<record from="icon716" to="graphics/pictures/club/716/icon"/>'
        '<record from="logo716" to="graphics/pictures/club/716/logo"/>'
    )
    assert pack_images(str(g), {("club", 716)}) == {("club", 716): str(logo)}
    assert icon.exists()
    assert pack_images(str(tmp_path / "nowhere"), {("club", 716)}) == {}
    (tmp_path / "games").mkdir()
    assert guess_graphics(str(tmp_path / "games")) == str(g)
    assert guess_graphics("") == ""
