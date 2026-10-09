import sys

from app.paths import data_directory, resource_root


def test_source_config_remains_in_project_data(monkeypatch):
    monkeypatch.delenv("YTCHAT_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert data_directory() == resource_root() / "data"


def test_frozen_resources_and_windows_config_are_separate(monkeypatch, tmp_path):
    monkeypatch.delenv("YTCHAT_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "unpacked"), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    assert resource_root() == tmp_path / "unpacked"
    assert data_directory() == tmp_path / "profile" / "YouTubeOBSChat"
    assert not data_directory().is_relative_to(resource_root())


def test_explicit_data_directory_wins_for_frozen_app(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("YTCHAT_DATA_DIR", str(tmp_path / "custom"))
    assert data_directory() == tmp_path / "custom"
