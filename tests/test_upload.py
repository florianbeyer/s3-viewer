from pathlib import Path

import pytest

from s3viewer.s3 import ConnectionSettings, S3Session
from s3viewer.upload import colliding_keys, folder_upload_plan, upload_destination_label, upload_plan, uploaded_message


def test_upload_plan_uses_the_open_folder_and_file_name():
    plan = upload_plan("daten/2024/", ["/tmp/eins.txt", "/home/a/zwei.csv"])
    assert plan == [("/tmp/eins.txt", "daten/2024/eins.txt"), ("/home/a/zwei.csv", "daten/2024/zwei.csv")]
    assert upload_destination_label("projekt", "daten/2024/") == "projekt/daten/2024/"
    assert upload_destination_label("projekt", "") == "projekt/"


def test_upload_plan_rejects_two_files_with_the_same_name():
    with pytest.raises(ValueError, match="bericht.txt"):
        upload_plan("", ["/tmp/a/bericht.txt", "/tmp/b/bericht.txt"])


def test_upload_sends_the_file_to_the_bucket_key(tmp_path: Path):
    source = tmp_path / "notiz.txt"
    source.write_text("hallo", encoding="utf-8")
    uploaded: list[tuple[str, str, str]] = []

    class Client:
        def upload_file(self, filename: str, bucket: str, key: str) -> None:
            uploaded.append((filename, bucket, key))

    session = S3Session(
        ConnectionSettings(endpoint_url="https://s3.example.com", access_key="ak", secret_key="sk"),
        client=Client(),
    )
    session.upload("projekt", "ordner/notiz.txt", str(source))
    assert uploaded == [(str(source), "projekt", "ordner/notiz.txt")]


def test_upload_and_download_forward_progress_chunks(tmp_path: Path):
    source = tmp_path / "notiz.txt"
    source.write_text("hallo", encoding="utf-8")
    seen: list[int] = []

    class Client:
        def upload_file(self, filename: str, bucket: str, key: str, Callback=None) -> None:
            assert filename == str(source)
            Callback(2)
            Callback(3)

        def download_file(self, bucket: str, key: str, filename: str, Callback=None) -> None:
            Callback(4)

    session = S3Session(
        ConnectionSettings(endpoint_url="https://s3.example.com", access_key="ak", secret_key="sk"),
        client=Client(),
    )
    session.upload("projekt", "ordner/notiz.txt", str(source), progress=seen.append)
    session.download("projekt", "ordner/notiz.txt", str(tmp_path / "kopie.txt"), progress=seen.append)
    assert seen == [2, 3, 4]


def test_put_text_sends_the_body_and_content_type():
    saved: dict = {}

    class Client:
        def put_object(self, **kwargs):
            saved.update(kwargs)

    session = S3Session(
        ConnectionSettings(endpoint_url="https://s3.example.com", access_key="ak", secret_key="sk"),
        client=Client(),
    )
    session.put_text("projekt", "note.txt", b"neu\n", "text/plain; charset=utf-8")
    assert saved["Bucket"] == "projekt"
    assert saved["Key"] == "note.txt"
    assert saved["Body"] == b"neu\n"
    assert saved["ContentType"] == "text/plain; charset=utf-8"


def test_folder_upload_keeps_subfolders(tmp_path: Path):
    root = tmp_path / "stapel"
    nested = root / "2020"
    nested.mkdir(parents=True)
    (nested / "a.tif").write_bytes(b"a")
    (root / "liesmich.txt").write_text("hallo", encoding="utf-8")
    plan = folder_upload_plan("images/", str(root))
    assert set(plan) == {
        (str(root / "liesmich.txt"), "images/stapel/liesmich.txt"),
        (str(nested / "a.tif"), "images/stapel/2020/a.tif"),
    }


def test_colliding_keys_only_lists_existing_names():
    plan = [("/tmp/neu.txt", "ordner/neu.txt"), ("/tmp/alt.txt", "ordner/alt.txt")]
    assert colliding_keys(plan, {"ordner/alt.txt"}) == ["ordner/alt.txt"]
    assert colliding_keys(plan, set()) == []
    assert uploaded_message(1, "projekt/daten/") == "1 Datei hochgeladen nach projekt/daten/"
    assert uploaded_message(2, "projekt/") == "2 Dateien hochgeladen nach projekt/"
