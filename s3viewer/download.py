"""Zielpfade für den Download mehrerer S3-Dateien."""

from __future__ import annotations

from pathlib import Path

from s3viewer.i18n import tr


def relative_name(prefix: str, key: str) -> str:
    if prefix and key.startswith(prefix):
        name = key[len(prefix) :]
    else:
        name = key
    return name.lstrip("/")


def destination_for(root: Path, relative: str) -> Path:
    parts: list[str] = []
    for part in relative.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(tr("bad_filename", name=relative))
        parts.append(part)
    if not parts:
        raise ValueError(tr("empty_filename"))
    root_resolved = root.resolve()
    target = root.joinpath(*parts)
    resolved = target.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(tr("bad_filename", name=relative))
    return target


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    number = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def saved_message(count: int, directory: str, capped: bool, limit: int) -> str:
    if count == 1:
        text = tr("saved_one", directory=directory)
    else:
        text = tr("saved_many", count=count, directory=directory)
    if capped:
        text += tr("saved_capped", limit=limit)
    return text
