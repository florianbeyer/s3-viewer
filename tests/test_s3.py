from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

from s3viewer.s3 import (
    ConnectionSettings,
    S3Session,
    entries_from_listing,
    humanize_error,
    normalize_endpoint,
    sort_entries,
    validate_settings,
)


def test_normalize_endpoint_accepts_host_without_scheme():
    assert normalize_endpoint(" s3.example.com/ ") == "https://s3.example.com"
    with pytest.raises(ValueError):
        normalize_endpoint("ftp://s3.example.com")


def test_validate_settings_requires_keys_and_hides_secret_in_redacted_form():
    settings = validate_settings(
        "https://s3.example.com/",
        " AK ",
        " geheim ",
        "",
        "mein-bucket",
        True,
        True,
        "s3v4",
    )
    assert settings.endpoint_url == "https://s3.example.com"
    assert settings.region == "us-east-1"
    assert settings.secret_key == "geheim"
    assert "geheim" not in settings.redacted()
    with pytest.raises(ValueError):
        validate_settings("https://s3.example.com", "ak", "", "us-east-1", "", True, True, "s3v4")


def test_entries_keep_one_folder_level_and_ignore_duplicate_markers():
    response = {
        "CommonPrefixes": [{"Prefix": "daten/"}],
        "Contents": [
            {"Key": "daten/", "Size": 0},
            {"Key": "readme.txt", "Size": 5, "LastModified": datetime(2024, 1, 2, tzinfo=timezone.utc)},
            {"Key": "logs/2024/app.log", "Size": 3},
        ],
    }
    entries = sort_entries(entries_from_listing("", response))
    assert [(entry.name, entry.is_folder, entry.key) for entry in entries] == [
        ("daten", True, "daten/"),
        ("logs", True, "logs/"),
        ("readme.txt", False, "readme.txt"),
    ]
    nested = entries_from_listing(
        "daten/",
        {"Contents": [{"Key": "daten/tabelle.csv", "Size": 4}, {"Key": "daten/sub/x.txt", "Size": 1}]},
    )
    assert {entry.name for entry in nested} == {"tabelle.csv", "sub"}


def test_signature_errors_are_explained_in_german():
    error = ClientError(
        {
            "Error": {"Code": "SignatureDoesNotMatch", "Message": "nope"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "ListBuckets",
    )
    text = humanize_error(error)
    assert "Signatur" in text
    assert "SignatureDoesNotMatch" in text


def test_list_falls_back_to_v1_when_v2_is_not_implemented():
    class FakeClient:
        def __init__(self):
            self.markers = []

        def list_objects_v2(self, **_kwargs):
            raise ClientError(
                {"Error": {"Code": "NotImplemented", "Message": "no"}, "ResponseMetadata": {"HTTPStatusCode": 501}},
                "ListObjectsV2",
            )

        def list_objects(self, **kwargs):
            self.markers.append(kwargs.get("Marker"))
            if kwargs.get("Marker") is None:
                return {
                    "IsTruncated": True,
                    "NextMarker": "a.txt",
                    "Contents": [{"Key": "a.txt", "Size": 1}],
                    "CommonPrefixes": [{"Prefix": "dir/"}],
                }
            return {"IsTruncated": False, "Contents": [{"Key": "b.txt", "Size": 2}]}

        def close(self):
            return None

    client = FakeClient()
    session = S3Session(_settings(), client=client)
    entries, capped = session.list_folder("bucket", "")
    assert capped is False
    assert client.markers == [None, "a.txt"]
    assert [entry.name for entry in entries] == ["dir", "a.txt", "b.txt"]


def test_access_denied_does_not_fall_back_to_v1():
    class FakeClient:
        def list_objects_v2(self, **_kwargs):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "no"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
                "ListObjectsV2",
            )

        def list_objects(self, **_kwargs):
            raise AssertionError("SigV2-Fallback darf bei Zugriff verweigert nicht laufen")

    session = S3Session(_settings(), client=FakeClient())
    with pytest.raises(ClientError):
        session.list_folder("bucket", "")


def test_cancelled_download_message_stays_short():
    from s3viewer.s3 import DownloadCancelled, humanize_error

    assert humanize_error(DownloadCancelled()) == "Download abgebrochen"


def test_list_file_keys_includes_nested_files_and_skips_folder_markers():
    class Client:
        def list_objects_v2(self, **kwargs):
            assert "Delimiter" not in kwargs
            assert kwargs["Prefix"] == "daten/"
            return {
                "IsTruncated": False,
                "Contents": [
                    {"Key": "daten/", "Size": 0},
                    {"Key": "daten/a.txt", "Size": 1},
                    {"Key": "daten/sub/b.txt", "Size": 2},
                    {"Key": "daten/leer/", "Size": 0},
                ],
            }

    session = S3Session(_settings(), client=Client())
    keys, capped = session.list_file_keys("bucket", "daten")
    assert keys == ["daten/a.txt", "daten/sub/b.txt"]
    assert capped is False
    records, capped = session.list_files("bucket", "daten")
    assert records == [("daten/a.txt", 1), ("daten/sub/b.txt", 2)]
    assert capped is False
    object_keys, capped = session.list_object_keys("bucket", "daten")
    assert object_keys == ["daten/a.txt", "daten/sub/b.txt", "daten/leer/"]
    assert capped is False


def test_delete_keys_batches_and_ignores_missing_objects():
    calls: list[dict] = []

    class Client:
        def delete_objects(self, **kwargs):
            calls.append(kwargs)
            return {"Errors": [{"Key": "weg", "Code": "NoSuchKey", "Message": "no"}]}

    session = S3Session(_settings(), client=Client())
    assert session.delete_keys("bucket", ["a.txt", "a.txt", "weg"]) == 2
    assert calls[0]["Bucket"] == "bucket"
    assert calls[0]["Delete"]["Objects"] == [{"Key": "a.txt"}, {"Key": "weg"}]


def test_delete_keys_falls_back_to_single_deletes():
    singles: list[str] = []

    class Client:
        def delete_objects(self, **_kwargs):
            raise ClientError(
                {"Error": {"Code": "NotImplemented", "Message": "no"}, "ResponseMetadata": {"HTTPStatusCode": 501}},
                "DeleteObjects",
            )

        def delete_object(self, **kwargs):
            singles.append(kwargs["Key"])

    session = S3Session(_settings(), client=Client())
    assert session.delete_keys("bucket", ["a.txt", "b/"]) == 2
    assert singles == ["a.txt", "b/"]


def _settings() -> ConnectionSettings:
    return ConnectionSettings(
        endpoint_url="https://s3.example.com",
        access_key="ak",
        secret_key="sk",
    )
