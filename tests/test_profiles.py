import os
from pathlib import Path

import pytest

from s3viewer.profiles import delete_profile, list_profile_names, load_profile, save_profile
from s3viewer.s3 import ConnectionSettings
from s3viewer.window import MainWindow
from tests.test_gui import FakeSession


def test_profile_is_stored_under_s3_viewer_with_private_permissions(tmp_path: Path):
    root = tmp_path / ".s3-viewer"
    saved = save_profile(root, "  Labor Nord  ", _settings())
    assert saved == "Labor Nord"
    loaded = load_profile(root, "Labor Nord")
    assert loaded.endpoint_url == "https://s3.example.com"
    assert loaded.secret_key == "geheim"
    assert loaded.direct_bucket == "projekt"
    assert list_profile_names(root) == ["Labor Nord"]
    assert (root.stat().st_mode & 0o777) == 0o700
    assert ((root / "connections.json").stat().st_mode & 0o777) == 0o600
    text = (root / "connections.json").read_text(encoding="utf-8")
    assert "geheim" in text

    delete_profile(root, "Labor Nord")
    assert list_profile_names(root) == []


def test_profile_name_rejects_slashes(tmp_path: Path):
    with pytest.raises(ValueError):
        save_profile(tmp_path, "a/b", _settings())


def test_saved_profile_fills_endpoint_and_secret(qtbot, tmp_path, monkeypatch):
    profiles = tmp_path / ".s3-viewer"
    settings_path = tmp_path / "ui.ini"
    monkeypatch.delenv("HOME", raising=False)
    window = MainWindow(
        session_factory=FakeSession,
        settings_path=str(settings_path),
        profiles_path=str(profiles),
    )
    qtbot.addWidget(window)
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("AKIA")
    window.secret_key.setText("super-geheim")
    window.region.setCurrentText("RegionOne")
    window.bucket_edit.setText("fotos")
    window._save_named_profile = lambda: None
    save_profile(
        profiles,
        "Nachtlauf",
        window._settings_from_form(),
    )
    window._reload_profiles(select="Nachtlauf")
    window.endpoint.clear()
    window.secret_key.clear()
    window.profile_combo.setCurrentIndex(0)
    window.profile_combo.setCurrentIndex(window.profile_combo.findData("Nachtlauf"))
    assert window.endpoint.text() == "https://s3.example.com"
    assert window.secret_key.text() == "super-geheim"
    assert window.region.currentText() == "RegionOne"
    assert window.region.findText("us-east-1") == 0
    assert window.region.findText("eu-central-1") >= 0
    assert window.bucket_edit.text() == "fotos"
    stored_ui = settings_path.read_text(encoding="utf-8") if settings_path.exists() else ""
    assert "super-geheim" not in stored_ui
    assert os.path.isdir(profiles)


def _settings() -> ConnectionSettings:
    return ConnectionSettings(
        endpoint_url="https://s3.example.com",
        access_key="ak",
        secret_key="geheim",
        region="RegionOne",
        direct_bucket="projekt",
        path_style=True,
        verify_ssl=False,
        signature_version="s3",
    )
