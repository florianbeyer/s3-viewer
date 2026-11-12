"""S3-Client für OpenStack- und andere kompatible Endpunkte."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse
import threading

from s3viewer.i18n import tr

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    ParamValidationError,
    PartialCredentialsError,
    ReadTimeoutError,
    SSLError,
)

MAX_LISTED = 5000
PAGE_SIZE = 1000


@dataclass(frozen=True)
class ConnectionSettings:
    endpoint_url: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"
    direct_bucket: str = ""
    path_style: bool = True
    verify_ssl: bool = True
    signature_version: str = "s3v4"

    def redacted(self) -> str:
        return (
            f"ConnectionSettings(endpoint_url={self.endpoint_url!r}, "
            f"access_key={self.access_key!r}, region={self.region!r}, "
            f"direct_bucket={self.direct_bucket!r}, path_style={self.path_style}, "
            f"verify_ssl={self.verify_ssl}, signature_version={self.signature_version})"
        )


@dataclass(frozen=True)
class BucketInfo:
    name: str
    created: datetime | None = None


@dataclass(frozen=True)
class ObjectEntry:
    name: str
    key: str
    is_folder: bool
    size: int | None = None
    last_modified: datetime | None = None


@dataclass(frozen=True)
class Connected:
    buckets: list[BucketInfo]
    notice: str | None = None


@dataclass(frozen=True)
class FetchedObject:
    data: bytes
    size: int
    content_type: str
    truncated: bool


def normalize_endpoint(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError(tr("err_endpoint_missing"))
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(tr("err_endpoint_url"))
    return url.rstrip("/")


def validate_settings(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    region: str,
    direct_bucket: str,
    path_style: bool,
    verify_ssl: bool,
    signature_version: str,
) -> ConnectionSettings:
    endpoint = normalize_endpoint(endpoint_url)
    access_key = access_key.strip()
    secret_key = secret_key.strip()
    region = region.strip() or "us-east-1"
    direct_bucket = direct_bucket.strip()
    if not access_key or not secret_key:
        raise ValueError(tr("err_keys_required"))
    if signature_version not in {"s3", "s3v4"}:
        raise ValueError(tr("err_signature"))
    if direct_bucket and ("/" in direct_bucket or any(char.isspace() for char in direct_bucket)):
        raise ValueError(tr("err_bucket_name"))
    return ConnectionSettings(
        endpoint_url=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        direct_bucket=direct_bucket,
        path_style=path_style,
        verify_ssl=verify_ssl,
        signature_version=signature_version,
    )


class DownloadCancelled(Exception):
    """Der Nutzer hat den Download abgebrochen."""


class CancelFlag:
    """Signalisiert einem laufenden Transfer, dass er stoppen soll."""

    def __init__(self) -> None:
        self._cancelled = False
        self._future: object | None = None
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            future = self._future
        cancel = getattr(future, "cancel", None)
        if cancel is not None:
            cancel()

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def attach(self, future: object) -> None:
        with self._lock:
            self._future = future
            already = self._cancelled
        if already:
            cancel = getattr(future, "cancel", None)
            if cancel is not None:
                cancel()


class _CancelDownload:
    def __init__(self, flag: CancelFlag, progress: Callable[[int], None] | None) -> None:
        self._flag = flag
        self._progress = progress

    def on_queued(self, future, **kwargs) -> None:
        self._flag.attach(future)

    def on_progress(self, future, bytes_transferred, **kwargs) -> None:
        if self._flag.cancelled:
            future.cancel()
            return
        if self._progress is not None and bytes_transferred:
            self._progress(int(bytes_transferred))


def humanize_error(exc: BaseException) -> str:
    if isinstance(exc, DownloadCancelled):
        return tr("download_cancelled")
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ClientError):
        return _humanize_client_error(exc)
    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ConnectionClosedError)):
        if _looks_like_tls(exc):
            return tr("err_tls")
        return tr("err_unreachable")
    if isinstance(exc, ReadTimeoutError):
        return tr("err_timeout")
    if isinstance(exc, SSLError) or _looks_like_tls(exc):
        return tr("err_tls")
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return tr("err_credentials")
    if isinstance(exc, ParamValidationError):
        return tr("err_invalid_connection")
    return f"{exc.__class__.__name__}: {exc}"


def _callback_for(
    progress: Callable[[int], None] | None,
    cancel: CancelFlag | None,
) -> Callable[[int], None] | None:
    if progress is None and cancel is None:
        return None

    def callback(amount: int) -> None:
        if cancel is not None and cancel.cancelled:
            raise DownloadCancelled()
        if progress is not None and amount:
            progress(int(amount))

    return callback


def entries_from_listing(prefix: str, response: dict[str, Any]) -> list[ObjectEntry]:
    """Liest eine ListObjects-Antwort als eine Ordnerebene."""
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    folders: dict[str, ObjectEntry] = {}
    files: dict[str, ObjectEntry] = {}

    def add_folder(relative: str) -> None:
        name = relative.strip("/").split("/", 1)[0]
        if not name:
            return
        key = f"{prefix}{name}/"
        folders[key] = ObjectEntry(name=name, key=key, is_folder=True)

    for common in response.get("CommonPrefixes") or []:
        add_folder(_relative(prefix, common.get("Prefix") or ""))

    for obj in response.get("Contents") or []:
        key = obj.get("Key") or ""
        if not key or key == prefix:
            continue
        relative = _relative(prefix, key)
        if not relative:
            continue
        name, separator, _rest = relative.partition("/")
        if separator or relative.endswith("/"):
            add_folder(name)
            continue
        if not name:
            continue
        size = obj.get("Size")
        files[key] = ObjectEntry(
            name=name,
            key=key,
            is_folder=False,
            size=int(size) if size is not None else 0,
            last_modified=obj.get("LastModified"),
        )
    return list(folders.values()) + list(files.values())


def sort_entries(entries: list[ObjectEntry]) -> list[ObjectEntry]:
    return sorted(entries, key=lambda entry: (0 if entry.is_folder else 1, entry.name.casefold()))


def dedupe_entries(entries: list[ObjectEntry]) -> list[ObjectEntry]:
    seen: set[str] = set()
    unique: list[ObjectEntry] = []
    for entry in entries:
        if entry.key in seen:
            continue
        seen.add(entry.key)
        unique.append(entry)
    return unique


class S3Session:
    def __init__(self, settings: ConnectionSettings, client: Any | None = None):
        self.settings = settings
        self._lock = threading.Lock()
        self._list_api = "v2"
        self._client = client or build_client(settings)
        if not settings.verify_ssl:
            _silence_tls_warnings()

    def establish(self) -> Connected:
        buckets: list[BucketInfo] = []
        list_error: BaseException | None = None
        try:
            buckets = self.list_buckets()
        except Exception as exc:
            list_error = exc
        direct = self.settings.direct_bucket
        if direct:
            self.ensure_bucket(direct)
            if all(bucket.name != direct for bucket in buckets):
                buckets.append(BucketInfo(name=direct))
            notice = None
            if list_error is not None:
                notice = tr("direct_bucket_notice")
            return Connected(buckets=_sort_buckets(buckets), notice=notice)
        if list_error is not None:
            raise list_error
        return Connected(buckets=_sort_buckets(buckets))

    def list_buckets(self) -> list[BucketInfo]:
        response = self._call(lambda: self._client.list_buckets())
        buckets = [
            BucketInfo(name=item["Name"], created=item.get("CreationDate"))
            for item in (response.get("Buckets") or [])
            if item.get("Name")
        ]
        return _sort_buckets(buckets)

    def ensure_bucket(self, bucket: str) -> None:
        self._page(bucket, "", None, max_keys=1)

    def list_folder(self, bucket: str, prefix: str) -> tuple[list[ObjectEntry], bool]:
        prefix = prefix or ""
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        collected: list[ObjectEntry] = []
        token: str | None = None
        capped = False
        while True:
            page, token = self._page(bucket, prefix, token, max_keys=PAGE_SIZE)
            collected.extend(page)
            if len(collected) >= MAX_LISTED:
                collected = collected[:MAX_LISTED]
                capped = True
                break
            if not token:
                break
        return sort_entries(dedupe_entries(collected)), capped

    def list_file_keys(self, bucket: str, prefix: str) -> tuple[list[str], bool]:
        """Alle Dateischlüssel unter einem Präfix, ohne Ordner-Platzhalter."""
        records, capped = self.list_files(bucket, prefix)
        return [key for key, _size in records], capped

    def list_files(self, bucket: str, prefix: str) -> tuple[list[tuple[str, int]], bool]:
        """Dateischlüssel und Größen unter einem Präfix, ohne Ordner-Platzhalter."""
        prefix = prefix or ""
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        records: list[tuple[str, int]] = []
        token: str | None = None
        capped = False
        while True:
            page, token = self._flat_page(bucket, prefix, token)
            records.extend(page)
            if len(records) >= MAX_LISTED:
                records = records[:MAX_LISTED]
                capped = True
                break
            if not token:
                break
        return records, capped

    def fetch(self, bucket: str, key: str, limit: int = 1_000_000) -> FetchedObject:
        meta = self._head(bucket, key)
        if meta is not None and meta.get("ContentLength") is not None:
            size = int(meta.get("ContentLength") or 0)
            content_type = meta.get("ContentType") or ""
            truncated = size > limit
            range_header = f"bytes=0-{limit - 1}" if truncated else None
            try:
                data, response_type, content_range, _length = self._get_bytes(bucket, key, limit, range_header)
            except ClientError:
                if not truncated:
                    raise
                data, response_type, content_range, _length = self._get_bytes(bucket, key, limit, None)
            total = _total_size(content_range, size)
            return FetchedObject(
                data=data,
                size=total,
                content_type=content_type or response_type,
                truncated=truncated or total > len(data),
            )

        data, response_type, content_range, length = self._get_bytes(bucket, key, limit + 1, None)
        truncated = len(data) > limit
        data = data[:limit]
        size = length if length is not None else len(data)
        size = _total_size(content_range, size)
        if truncated:
            size = max(size, limit + 1)
        return FetchedObject(
            data=data,
            size=size,
            content_type=response_type,
            truncated=truncated,
        )

    def _get_bytes(
        self,
        bucket: str,
        key: str,
        limit: int,
        range_header: str | None,
    ) -> tuple[bytes, str, str | None, int | None]:
        def run() -> tuple[bytes, str, str | None, int | None]:
            kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
            if range_header:
                kwargs["Range"] = range_header
            response = self._client.get_object(**kwargs)
            body = response["Body"]
            try:
                data = body.read(limit)
            finally:
                body.close()
            length = response.get("ContentLength")
            return (
                data,
                response.get("ContentType") or "",
                response.get("ContentRange"),
                int(length) if length is not None else None,
            )

        return self._call(run)

    def download(
        self,
        bucket: str,
        key: str,
        destination: str,
        *,
        progress: Callable[[int], None] | None = None,
        cancel: CancelFlag | None = None,
    ) -> None:
        def run() -> None:
            if cancel is not None and cancel.cancelled:
                raise DownloadCancelled()
            if cancel is not None and hasattr(self._client, "meta"):
                self._download_managed(bucket, key, destination, progress, cancel)
                return
            callback = _callback_for(progress, cancel)
            if callback is None:
                self._client.download_file(bucket, key, destination)
                return
            self._client.download_file(bucket, key, destination, Callback=callback)

        self._call(run)

    def _download_managed(
        self,
        bucket: str,
        key: str,
        destination: str,
        progress: Callable[[int], None] | None,
        cancel: CancelFlag,
    ) -> None:
        from boto3.s3.transfer import TransferConfig, create_transfer_manager
        from s3transfer.exceptions import CancelledError

        manager = create_transfer_manager(self._client, TransferConfig(preferred_transfer_client="classic"))
        subscriber = _CancelDownload(cancel, progress)
        try:
            future = manager.download(bucket, key, destination, subscribers=[subscriber])
            cancel.attach(future)
            try:
                future.result()
            except CancelledError as exc:
                raise DownloadCancelled() from exc
        finally:
            shutdown = getattr(manager, "shutdown", None)
            if shutdown is not None:
                shutdown()

    def upload(
        self,
        bucket: str,
        key: str,
        source: str,
        *,
        progress: Callable[[int], None] | None = None,
    ) -> None:
        def run() -> None:
            if progress is None:
                self._client.upload_file(source, bucket, key)
                return
            self._client.upload_file(source, bucket, key, Callback=progress)

        self._call(run)

    def put_text(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        def run() -> None:
            self._client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

        self._call(run)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is None:
            return
        with self._lock:
            close()

    def _head(self, bucket: str, key: str) -> dict[str, Any] | None:
        try:
            return self._call(lambda: self._client.head_object(Bucket=bucket, Key=key))
        except ClientError as exc:
            code = _error_code(exc)
            if code in {"NoSuchKey", "404", "NotFound", "NoSuchBucket"}:
                raise
            return None

    def _page(
        self,
        bucket: str,
        prefix: str,
        token: str | None,
        max_keys: int,
    ) -> tuple[list[ObjectEntry], str | None]:
        if self._list_api == "v2":
            try:
                response, next_token = self._page_v2(bucket, prefix, token, max_keys)
                return entries_from_listing(prefix, response), next_token
            except ClientError as exc:
                if token is None and _unsupported(exc):
                    self._list_api = "v1"
                else:
                    raise
        response, next_token = self._page_v1(bucket, prefix, token, max_keys)
        return entries_from_listing(prefix, response), next_token

    def _page_v2(
        self,
        bucket: str,
        prefix: str,
        token: str | None,
        max_keys: int,
    ) -> tuple[dict[str, Any], str | None]:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": prefix,
            "Delimiter": "/",
            "MaxKeys": max_keys,
        }
        if token:
            kwargs["ContinuationToken"] = token
        response = self._call(lambda: self._client.list_objects_v2(**kwargs))
        next_token = response.get("NextContinuationToken") if response.get("IsTruncated") else None
        return response, next_token

    def _page_v1(
        self,
        bucket: str,
        prefix: str,
        token: str | None,
        max_keys: int,
    ) -> tuple[dict[str, Any], str | None]:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": prefix,
            "Delimiter": "/",
            "MaxKeys": max_keys,
        }
        if token:
            kwargs["Marker"] = token
        response = self._call(lambda: self._client.list_objects(**kwargs))
        next_token = None
        if response.get("IsTruncated"):
            next_token = response.get("NextMarker")
            if not next_token:
                contents = response.get("Contents") or []
                prefixes = response.get("CommonPrefixes") or []
                if contents:
                    next_token = contents[-1].get("Key")
                elif prefixes:
                    next_token = prefixes[-1].get("Prefix")
        return response, next_token

    def _flat_page(self, bucket: str, prefix: str, token: str | None) -> tuple[list[tuple[str, int]], str | None]:
        if self._list_api == "v2":
            try:
                response, next_token = self._flat_v2(bucket, prefix, token)
                return _file_records(prefix, response), next_token
            except ClientError as exc:
                if token is None and _unsupported(exc):
                    self._list_api = "v1"
                else:
                    raise
        response, next_token = self._flat_v1(bucket, prefix, token)
        return _file_records(prefix, response), next_token

    def _flat_v2(self, bucket: str, prefix: str, token: str | None) -> tuple[dict[str, Any], str | None]:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": PAGE_SIZE}
        if token:
            kwargs["ContinuationToken"] = token
        response = self._call(lambda: self._client.list_objects_v2(**kwargs))
        next_token = response.get("NextContinuationToken") if response.get("IsTruncated") else None
        return response, next_token

    def _flat_v1(self, bucket: str, prefix: str, token: str | None) -> tuple[dict[str, Any], str | None]:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": PAGE_SIZE}
        if token:
            kwargs["Marker"] = token
        response = self._call(lambda: self._client.list_objects(**kwargs))
        next_token = None
        if response.get("IsTruncated"):
            contents = response.get("Contents") or []
            next_token = response.get("NextMarker") or (contents[-1].get("Key") if contents else None)
        return response, next_token

    def _call(self, fn: Callable[[], Any]) -> Any:
        with self._lock:
            return fn()


def build_client(settings: ConnectionSettings) -> Any:
    addressing = "path" if settings.path_style else "auto"
    config_kwargs: dict[str, Any] = {
        "signature_version": settings.signature_version,
        "s3": {"addressing_style": addressing},
        "connect_timeout": 8,
        "read_timeout": 60,
        "retries": {"max_attempts": 2, "mode": "standard"},
        "request_checksum_calculation": "when_required",
        "response_checksum_validation": "when_required",
    }
    try:
        config = Config(**config_kwargs)
    except TypeError:
        config_kwargs.pop("request_checksum_calculation", None)
        config_kwargs.pop("response_checksum_validation", None)
        config = Config(**config_kwargs)
    session = boto3.session.Session(
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
    )
    return session.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        config=config,
        verify=settings.verify_ssl,
    )


def _file_records(prefix: str, response: dict[str, Any]) -> list[tuple[str, int]]:
    records: list[tuple[str, int]] = []
    for obj in response.get("Contents") or []:
        key = obj.get("Key") or ""
        if not key or key == prefix or key.endswith("/"):
            continue
        if prefix and not key.startswith(prefix):
            continue
        size = obj.get("Size")
        records.append((key, int(size) if size is not None else 0))
    return records


def _relative(prefix: str, key: str) -> str:
    if prefix and key.startswith(prefix):
        return key[len(prefix) :]
    if prefix:
        return ""
    return key


def _sort_buckets(buckets: list[BucketInfo]) -> list[BucketInfo]:
    return sorted(buckets, key=lambda bucket: bucket.name.casefold())


def _error_code(exc: ClientError) -> str:
    error = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
    return str(error.get("Code") or "")


def _status_code(exc: ClientError) -> int | None:
    if not isinstance(exc.response, dict):
        return None
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return int(status) if status is not None else None


def _unsupported(exc: ClientError) -> bool:
    if _status_code(exc) == 501 or _error_code(exc) in {"NotImplemented", "XNotImplemented"}:
        return True
    message = ""
    if isinstance(exc.response, dict):
        message = str(exc.response.get("Error", {}).get("Message") or "")
    return "not implemented" in message.lower()


def _looks_like_tls(exc: BaseException) -> bool:
    text = f"{exc.__class__.__name__} {exc}".lower()
    return "ssl" in text or "certificate" in text or "tls" in text


def _total_size(content_range: str | None, fallback: int) -> int:
    if not content_range or "/" not in content_range:
        return fallback
    total = content_range.rsplit("/", 1)[-1]
    if total == "*":
        return fallback
    try:
        return int(total)
    except ValueError:
        return fallback


def _humanize_client_error(exc: ClientError) -> str:
    code = _error_code(exc) or "Unbekannt"
    status = _status_code(exc)
    messages = {
        "InvalidAccessKeyId": tr("err_access_key"),
        "SignatureDoesNotMatch": tr("err_sig_mismatch"),
        "AccessDenied": tr("err_access_denied"),
        "AllAccessDisabled": tr("err_access_disabled"),
        "NoSuchBucket": tr("err_no_bucket"),
        "NoSuchKey": tr("err_no_key"),
        "InvalidBucketName": tr("err_bad_bucket"),
        "AuthorizationHeaderMalformed": tr("err_auth_header"),
        "PermanentRedirect": tr("err_redirect"),
        "RequestTimeTooSkewed": tr("err_clock"),
        "InvalidArgument": tr("err_argument"),
    }
    if code in messages:
        return tr("err_with_code", message=messages[code], code=code)
    if status == 501 or code in {"NotImplemented", "XNotImplemented"}:
        return tr("err_not_implemented", code=code)
    if status == 403:
        return tr("err_forbidden", code=code)
    error = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
    detail = error.get("Message") or ""
    if detail:
        return tr("err_with_code", message=detail, code=code)
    return tr("err_failed", code=code)


def _silence_tls_warnings() -> None:
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        return
