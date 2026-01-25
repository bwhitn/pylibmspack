from __future__ import annotations

import os
import posixpath
import re


_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def normalize_member_path(name: str) -> str:
    """Normalize an archive member path for safe extraction."""
    if "\x00" in name:
        raise ValueError("NUL byte in member name")
    raw = name.replace("\\", "/")
    if _DRIVE_RE.match(raw):
        raise ValueError("Drive-letter paths are not allowed")
    if raw.startswith("//"):
        raise ValueError("UNC paths are not allowed")
    if raw.startswith("/"):
        raise ValueError("Absolute paths are not allowed")
    norm = posixpath.normpath(raw)
    if norm in {".", ""}:
        raise ValueError("Empty member path")
    if norm.startswith("../") or norm == "..":
        raise ValueError("Path traversal is not allowed")
    if norm.startswith("/"):
        raise ValueError("Absolute paths are not allowed")
    return norm


def safe_join(dest_dir: str, name: str) -> str:
    norm = normalize_member_path(name)
    dest_dir_abs = os.path.abspath(dest_dir)
    target = os.path.abspath(os.path.join(dest_dir_abs, *norm.split("/")))
    if os.path.commonpath([dest_dir_abs, target]) != dest_dir_abs:
        raise ValueError("Path traversal is not allowed")
    return target


def unsafe_join(dest_dir: str, name: str) -> str:
    parts = name.replace("\\", "/").split("/")
    return os.path.join(dest_dir, *parts)


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
