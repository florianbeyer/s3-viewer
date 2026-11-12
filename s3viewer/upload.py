"""Zielschlüssel für Uploads in den geöffneten Bucket-Ordner."""

from __future__ import annotations

from pathlib import Path

from s3viewer.i18n import tr


def upload_key(prefix: str, local_path: str) -> str:
    name = Path(local_path).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(tr("upload_bad_path", path=local_path))
    folder = prefix or ""
    if folder and not folder.endswith("/"):
        folder += "/"
    return f"{folder}{name}"


def upload_plan(prefix: str, local_paths: list[str]) -> list[tuple[str, str]]:
    plan: list[tuple[str, str]] = []
    seen: set[str] = set()
    for local_path in local_paths:
        key = upload_key(prefix, local_path)
        name = key.rsplit("/", 1)[-1]
        if name in seen:
            raise ValueError(tr("upload_duplicate", name=name))
        seen.add(name)
        plan.append((local_path, key))
    if not plan:
        raise ValueError(tr("upload_none"))
    return plan


def folder_upload_plan(prefix: str, directory: str) -> list[tuple[str, str]]:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(tr("not_a_folder"))
    folder_name = root.name
    if not folder_name or folder_name in {".", ".."}:
        raise ValueError(tr("bad_folder"))
    folder = prefix or ""
    if folder and not folder.endswith("/"):
        folder += "/"
    folder += folder_name + "/"
    plan: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
            continue
        plan.append((str(path), folder + relative))
    if not plan:
        raise ValueError(tr("folder_empty_local"))
    return plan


def colliding_keys(plan: list[tuple[str, str]], existing_keys: set[str]) -> list[str]:
    return [key for _source, key in plan if key in existing_keys]


def upload_destination_label(bucket: str, prefix: str) -> str:
    folder = prefix.strip("/")
    if folder:
        return f"{bucket}/{folder}/"
    return f"{bucket}/"


def uploaded_message(count: int, destination: str) -> str:
    if count == 1:
        return tr("uploaded_one", destination=destination)
    return tr("uploaded_many", count=count, destination=destination)
