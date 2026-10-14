import os

import pytest

from fmcareer import app
from fmcareer.images import _folders
from fmcareer.install import clean_path, database_dir, licensed_data_dir, looks_like_saves
from fmcareer.names import lang_files

MAC_DB = (
    "fm.app",
    "Contents",
    "PlugIns",
    "game_plugin.bundle",
    "Contents",
    "Resources",
    "shared",
    "data",
    "database",
    "db",
)
MAC_ASSETS = ("fm.app", "Contents", "Resources", "Data", "StreamingAssets", "LicensedData")


def game(tmp_path, db, assets):
    install = tmp_path / "Football Manager 26"
    lang = install.joinpath(*db, "2600", "2600_fm", "lang_db.dat")
    lang.parent.mkdir(parents=True)
    lang.write_bytes(b"")
    (install.joinpath(*assets) / "Core").mkdir(parents=True)
    return install


@pytest.fixture
def mac(tmp_path):
    return game(tmp_path, MAC_DB, MAC_ASSETS)


@pytest.fixture
def windows(tmp_path):
    return game(tmp_path, ("shared", "data", "database", "db"), ("fm_Data", "StreamingAssets", "LicensedData"))


def test_windows_install_is_read_from_its_folder(windows):
    assert database_dir(str(windows)) == str(windows / "shared" / "data" / "database" / "db")
    assert len(lang_files(str(windows))) == 1
    assert _folders(str(windows)) == [str(windows / "fm_Data" / "StreamingAssets" / "LicensedData" / "Core")]


@pytest.mark.parametrize("picked", [(), ("fm.app",), ("fm.app", "Contents"), MAC_DB, MAC_ASSETS])
def test_mac_install_is_found_inside_the_app_bundle(mac, picked):
    folder = str(mac.joinpath(*picked))
    assert database_dir(folder) == str(mac.joinpath(*MAC_DB))
    assert licensed_data_dir(folder) == str(mac.joinpath(*MAC_ASSETS))
    assert len(lang_files(folder)) == 1


def test_other_folders_are_not_an_install(tmp_path):
    assert database_dir(str(tmp_path)) is None and licensed_data_dir(str(tmp_path)) is None
    assert database_dir("") is None and lang_files("") == [] and _folders(str(tmp_path)) == []


@pytest.mark.skipif(os.sep != "/", reason="Terminal-style escapes are a macOS and Linux thing")
def test_pasted_paths_are_cleaned(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/me")
    assert clean_path('  "/Users/me/Football Manager 26"  ') == "/Users/me/Football Manager 26"
    assert clean_path("~/Library/Application Support") == "/Users/me/Library/Application Support"
    assert (
        clean_path(r"/Users/me/Steam/steamapps/common/Football\ Manager\ 26")
        == "/Users/me/Steam/steamapps/common/Football Manager 26"
    )
    assert clean_path("   ") == ""


def test_the_saves_folder_is_told_apart_from_the_install(tmp_path):
    user = tmp_path / "Sports Interactive" / "Football Manager 26"
    (user / "games").mkdir(parents=True)
    assert looks_like_saves(str(user)) and app.names_status(str(user)) == "saves_folder"
    assert app.names_status(str(tmp_path)) == "bad_install"
