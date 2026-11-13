"""Kopieren und Einfügen von Dateien innerhalb eines Buckets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CopiedObject:
    bucket: str
    key: str
    name: str
    is_folder: bool


def paste_pairs(item: CopiedObject, dest_prefix: str, nested_keys: list[str]) -> list[tuple[str, str, str]]:
    """Liefert (Quell-Bucket, Quell-Schlüssel, Ziel-Schlüssel) für ein kopiertes Objekt."""
    folder = dest_prefix or ""
    if folder and not folder.endswith("/"):
        folder += "/"
    if not item.is_folder:
        return [(item.bucket, item.key, f"{folder}{item.name}")]
    source = item.key if item.key.endswith("/") else f"{item.key}/"
    suffix = f"{item.name}/"
    parent = source[: -len(suffix)] if source.endswith(suffix) else ""
    keys = list(nested_keys)
    if source not in keys:
        keys.append(source)
    pairs: list[tuple[str, str, str]] = []
    for key in keys:
        if parent and key.startswith(parent):
            relative = key[len(parent) :]
        else:
            relative = key
        if not relative:
            continue
        pairs.append((item.bucket, key, f"{folder}{relative}"))
    return pairs
