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


def ensure_safe_output_path(dest_dir: str, target: str) -> None:
    """Reject symlinked safe extraction paths before opening output files."""
    dest_dir_abs = os.path.abspath(dest_dir)
    target_abs = os.path.abspath(target)
    if os.path.commonpath([dest_dir_abs, target_abs]) != dest_dir_abs:
        raise ValueError("Path traversal is not allowed")
    if os.path.islink(dest_dir_abs):
        raise ValueError("Destination directory must not be a symlink")

    rel = os.path.relpath(target_abs, dest_dir_abs)
    if rel in {".", ""}:
        raise ValueError("Output path must be inside destination directory")
    parts = rel.split(os.sep)
    current = dest_dir_abs
    for part in parts[:-1]:
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise ValueError("Output path must not contain symlinks")
    if os.path.islink(target_abs):
        raise ValueError("Output path must not be a symlink")


def remove_partial_output(path: str) -> None:
    try:
        if os.path.lexists(path):
            os.unlink(path)
    except OSError:
        pass


def unsafe_join(dest_dir: str, name: str) -> str:
    parts = name.replace("\\", "/").split("/")
    return os.path.join(dest_dir, *parts)


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
