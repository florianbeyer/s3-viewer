"""Benannte Verbindungen im üblichen, versteckten Konfigurationsordner des Systems."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from s3viewer.i18n import tr
from s3viewer.s3 import ConnectionSettings


def platform_config_dir() -> Path:
    """Hidden, OS-typical folder for settings and saved credentials."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "s3-viewer"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "s3-viewer"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "s3-viewer"


def config_dir_display() -> str:
    if sys.platform == "win32":
        return r"%AppData%\s3-viewer"
    if sys.platform == "darwin":
        return "~/Library/Application Support/s3-viewer"
    if os.environ.get("XDG_CONFIG_HOME"):
        return str(platform_config_dir())
    return "~/.config/s3-viewer"


def default_profiles_root() -> Path:
    dest = platform_config_dir()
    _import_legacy_connections(dest)
    return dest


def settings_ini_path() -> Path:
    dest = platform_config_dir() / "settings.ini"
    if not dest.exists():
        legacy = Path.home() / ".config" / "s3viewer" / "S3Viewer.conf"
        if legacy.is_file():
            _ensure_private(dest.parent)
            shutil.copy2(legacy, dest)
    return dest


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


def _import_legacy_connections(dest: Path) -> None:
    target = dest / "connections.json"
    if target.exists():
        return
    legacy = Path.home() / ".s3-viewer" / "connections.json"
    if not legacy.is_file() or legacy.resolve() == target.resolve():
        return
    _ensure_private(dest)
    shutil.copy2(legacy, target)
    _chmod(target, 0o600)


def _ensure_private(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _chmod(directory, 0o700)


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        return


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
    _ensure_private(root)
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
    _chmod(target, 0o600)
