from pathlib import Path

import pytest

from s3viewer.download import destination_for, relative_name, saved_message, unique_path


def test_relative_name_keeps_the_folder():
    assert relative_name("logs/2024/", "logs/2024/app/x.txt") == "app/x.txt"
    assert relative_name("", "daten/a.txt") == "daten/a.txt"


def test_destination_rejects_parent_segments(tmp_path: Path):
    assert destination_for(tmp_path, "ordner/datei.txt") == tmp_path / "ordner" / "datei.txt"
    with pytest.raises(ValueError):
        destination_for(tmp_path, "../geheim.txt")
    with pytest.raises(ValueError):
        destination_for(tmp_path, "ordner/../../geheim.txt")


def test_unique_path_adds_a_number_when_the_file_exists(tmp_path: Path):
    original = tmp_path / "bericht.txt"
    original.write_text("alt", encoding="utf-8")
    assert unique_path(original) == tmp_path / "bericht (2).txt"
    (tmp_path / "bericht (2).txt").write_text("auch", encoding="utf-8")
    assert unique_path(original) == tmp_path / "bericht (3).txt"


def test_saved_message_uses_singular_and_mentions_the_limit():
    assert saved_message(1, "/tmp/ziel", False, 5000) == "1 Datei gespeichert in /tmp/ziel"
    assert "2 Dateien" in saved_message(2, "/tmp/ziel", False, 5000)
    assert "5000" in saved_message(2, "/tmp/ziel", True, 5000)
