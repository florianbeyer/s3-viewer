"""Benannte Verbindungen im Home-Verzeichnis unter .s3-viewer."""

from __future__ import annotations

import json
import os
from pathlib import Path

from s3viewer.i18n import tr
from s3viewer.s3 import ConnectionSettings

def default_profiles_root() -> Path:
    return Path.home() / ".s3-viewer"


def list_profile_names(root: Path) -> list[str]:
    return sorted(_read(root), key=str.casefold)


def load_profile(root: Path, name: str) -> ConnectionSettings:
    profiles = _read(root)
    if name not in profiles:
        raise ValueError(tr("profile_missing", name=name))
    data = profiles[name]
    try:
        return ConnectionSettings(
            endpoint_url=str(data["endpoint_url"]),
            access_key=str(data["access_key"]),
            secret_key=str(data["secret_key"]),
            region=str(data.get("region") or "us-east-1"),
            direct_bucket=str(data.get("direct_bucket") or ""),
            path_style=bool(data.get("path_style", True)),
            verify_ssl=bool(data.get("verify_ssl", True)),
            signature_version=str(data.get("signature_version") or "s3v4"),
        )
    except KeyError as exc:
        raise ValueError(tr("profile_incomplete", name=name)) from exc


def save_profile(root: Path, name: str, settings: ConnectionSettings) -> str:
    cleaned = normalize_profile_name(name)
    profiles = _read(root)
    profiles[cleaned] = {
        "endpoint_url": settings.endpoint_url,
        "access_key": settings.access_key,
        "secret_key": settings.secret_key,
        "region": settings.region,
        "direct_bucket": settings.direct_bucket,
        "path_style": settings.path_style,
        "verify_ssl": settings.verify_ssl,
        "signature_version": settings.signature_version,
    }
    _write(root, profiles)
    return cleaned


def delete_profile(root: Path, name: str) -> None:
    profiles = _read(root)
    if name not in profiles:
        raise ValueError(tr("profile_missing", name=name))
    del profiles[name]
    _write(root, profiles)


def normalize_profile_name(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        raise ValueError(tr("profile_needs_name"))
    if "/" in cleaned or "\\" in cleaned or len(cleaned) > 80:
        raise ValueError(tr("profile_bad_name"))
    return cleaned


def _store_path(root: Path) -> Path:
    return root / "connections.json"


def _read(root: Path) -> dict[str, dict]:
    path = _store_path(root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(tr("profile_unreadable")) from exc
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError(tr("profile_unreadable"))
    return {str(name): value for name, value in profiles.items() if isinstance(value, dict)}


def _write(root: Path, profiles: dict[str, dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    target = _store_path(root)
    temporary = root / "connections.json.tmp"
    payload = json.dumps({"version": 1, "profiles": profiles}, indent=2, ensure_ascii=False)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    os.chmod(target, 0o600)
