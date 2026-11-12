import socket
from pathlib import Path

import boto3
import pytest
from botocore.config import Config

from s3viewer.preview import build_preview
from s3viewer.s3 import S3Session, validate_settings


def test_session_browses_an_s3_endpoint(tmp_path: Path):
    moto = pytest.importorskip("moto.server")
    port = _free_port()
    server = moto.ThreadedMotoServer(port=port)
    server.start()
    endpoint = f"http://127.0.0.1:{port}"
    try:
        _wait_until_up(endpoint)
        seed = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        seed.create_bucket(Bucket="projekt")
        seed.put_object(Bucket="projekt", Key="readme.txt", Body=b"Hallo Welt\n")
        seed.put_object(Bucket="projekt", Key="daten/tabelle.csv", Body="Name;Wert\nAlpha;1\n".encode())
        seed.put_object(Bucket="projekt", Key="daten/config.json", Body=b'{"ok": true}')
        seed.put_object(Bucket="projekt", Key="daten/note.xml", Body=b"<root><item>A</item></root>")
        seed.put_object(Bucket="projekt", Key="daten/bild.png", Body=b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
        seed.put_object(Bucket="projekt", Key="logs/2024/app.log", Body=b"zeile\n")

        session = S3Session(
            validate_settings(endpoint, "test", "test", "us-east-1", "", True, False, "s3v4")
        )
        try:
            connected = session.establish()
            assert [bucket.name for bucket in connected.buckets] == ["projekt"]
            root, capped = session.list_folder("projekt", "")
            assert capped is False
            assert {entry.name for entry in root} == {"readme.txt", "daten", "logs"}
            daten, _capped = session.list_folder("projekt", "daten/")
            assert {entry.name for entry in daten} == {"tabelle.csv", "config.json", "note.xml", "bild.png"}
            fetched = session.fetch("projekt", "daten/config.json")
            preview = build_preview(
                "daten/config.json",
                fetched.data,
                content_type=fetched.content_type,
                size=fetched.size,
                truncated=fetched.truncated,
            )
            assert '"ok": true' in preview.text
            destination = tmp_path / "readme.txt"
            session.download("projekt", "readme.txt", str(destination))
            assert destination.read_text(encoding="utf-8") == "Hallo Welt\n"
        finally:
            session.close()
    finally:
        server.stop()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_up(endpoint: str) -> None:
    import time

    import urllib3

    deadline = time.monotonic() + 10
    last_error = ""
    while time.monotonic() < deadline:
        try:
            urllib3.PoolManager().request("GET", endpoint, timeout=0.5, retries=False)
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.05)
    raise RuntimeError(f"Moto-Server nicht erreichbar: {last_error}")
