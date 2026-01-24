from __future__ import annotations

import os
import posixpath
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional, TypedDict

from . import _cab
from .errors import (
    CabDecompressionError,
    CabError,
    CabFormatError,
    CabPathTraversalError,
)


_ERR_OK = getattr(_cab, "MSPACK_ERR_OK", 0)
_ERR_DATAFORMAT = getattr(_cab, "MSPACK_ERR_DATAFORMAT", -1)
_ERR_DECRUNCH = getattr(_cab, "MSPACK_ERR_DECRUNCH", -1)
_ERR_BADCOMP = getattr(_cab, "MSPACK_ERR_BADCOMP", -1)


def _raise_for_err(err: int, context: str) -> None:
    if err == _ERR_OK:
        return
    if err in {_ERR_DATAFORMAT, _ERR_BADCOMP}:
        raise CabFormatError(f"{context} failed: libmspack error {err}")
    if err == _ERR_DECRUNCH:
        raise CabDecompressionError(f"{context} failed: libmspack error {err}")
    raise CabError(f"{context} failed: libmspack error {err}")


_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _normalize_member_path(name: str) -> str:
    if "\x00" in name:
        raise CabPathTraversalError("NUL byte in member name")
    raw = name.replace("\\", "/")
    if _DRIVE_RE.match(raw):
        raise CabPathTraversalError("Drive-letter paths are not allowed")
    if raw.startswith("//"):
        raise CabPathTraversalError("UNC paths are not allowed")
    if raw.startswith("/"):
        raise CabPathTraversalError("Absolute paths are not allowed")
    norm = posixpath.normpath(raw)
    if norm in {".", ""}:
        raise CabPathTraversalError("Empty member path")
    if norm.startswith("../") or norm == "..":
        raise CabPathTraversalError("Path traversal is not allowed")
    if norm.startswith("/"):
        raise CabPathTraversalError("Absolute paths are not allowed")
    return norm


def _safe_join(dest_dir: str, name: str) -> str:
    norm = _normalize_member_path(name)
    dest_dir_abs = os.path.abspath(dest_dir)
    target = os.path.abspath(os.path.join(dest_dir_abs, *norm.split("/")))
    if os.path.commonpath([dest_dir_abs, target]) != dest_dir_abs:
        raise CabPathTraversalError("Path traversal is not allowed")
    return target


def _unsafe_join(dest_dir: str, name: str) -> str:
    parts = name.replace("\\", "/").split("/")
    return os.path.join(dest_dir, *parts)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


class CabFileInfo(TypedDict):
    """Typed metadata for a CAB member."""

    name: str
    size: int
    dos_date: int
    dos_time: int
    date_y: int
    date_m: int
    date_d: int
    time_h: int
    time_m: int
    time_s: int
    datetime_utc: str
    attrs: int
    is_readonly: bool
    is_hidden: bool
    is_system: bool
    is_archive: bool
    folder_index: int
    offset: int
    compression: str
    has_prev: bool
    has_next: bool
    prev_cabinet: Optional[str]
    next_cabinet: Optional[str]
    cabinet_set_id: Optional[int]
    cabinet_set_index: Optional[int]


class CabInfo(TypedDict):
    """Typed metadata for a CAB header."""

    filename: Optional[str]
    base_offset: int
    length: int
    set_id: int
    set_index: int
    header_resv: int
    flags: int
    has_prev: bool
    has_next: bool
    prev_cabinet: Optional[str]
    next_cabinet: Optional[str]
    prev_disk: Optional[str]
    next_disk: Optional[str]
    files_count: int
    folders_count: int


class CabArchive:
    """Read and extract files from a CAB archive.

    Parameters
    ----------
    path:
        Path to a CAB file on disk.
    """

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None

    @classmethod
    def from_bytes(cls, data: bytes) -> "CabArchive":
        """Create an archive backed by an in-memory CAB buffer.

        Parameters
        ----------
        data:
            CAB file contents as bytes.
        """
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        return obj

    def files(self) -> list[CabFileInfo]:
        """Return metadata for each member in the CAB.

        Each dict includes:
        - name (str)
        - size (int)
        - dos_date (int)
        - dos_time (int)
        - date_y/date_m/date_d (int)
        - time_h/time_m/time_s (int)
        - datetime_utc (str, ISO 8601)
        - attrs (int)
        - is_readonly/is_hidden/is_system/is_archive (bool)
        - folder_index (int)
        - offset (int)
        - compression (str): none/mszip/quantum/lzx
        - has_prev/has_next (bool)
        - prev_cabinet/next_cabinet (str|None)
        - cabinet_set_id/cabinet_set_index (int|None)
        """
        if self._data is not None:
            files, err = _cab.list_files_bytes(self._data)
        else:
            files, err = _cab.list_files(self.path)
        _raise_for_err(err, "listing")
        if files is None:
            return []
        for entry in files:
            try:
                dt = datetime(
                    int(entry.get("date_y", 0)),
                    int(entry.get("date_m", 0)),
                    int(entry.get("date_d", 0)),
                    int(entry.get("time_h", 0)),
                    int(entry.get("time_m", 0)),
                    int(entry.get("time_s", 0)),
                    tzinfo=timezone.utc,
                )
                entry["datetime_utc"] = dt.isoformat()
            except Exception:
                entry["datetime_utc"] = ""
        return files

    def info(self) -> CabInfo:
        """Return parsed CAB header information.

        Includes header fields such as flags, set ID/index, sizes, and
        linkage to previous/next cabinets.
        """
        if self._data is not None:
            info, err = _cab.cab_info_bytes(self._data)
        else:
            info, err = _cab.cab_info(self.path)
        _raise_for_err(err, "info")
        if info is None:
            raise CabError("info failed: no data")
        return info

    def read(self, name: str, *, max_size: int = 256 * 1024 * 1024) -> bytes:
        """Extract a member and return its bytes.

        Parameters
        ----------
        name:
            Member name within the CAB.
        max_size:
            Maximum allowed size in bytes. Defaults to 256 MiB.

        Raises
        ------
        CabError
            If extraction fails or the member exceeds max_size.
        CabPathTraversalError
            If the member name is unsafe.
        """
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_path = _safe_join(tmp, name)
            _ensure_parent(out_path)
            if self._data is not None:
                err = _cab.extract_file_bytes(self._data, name, out_path)
            else:
                err = _cab.extract_file(self.path, name, out_path)
            _raise_for_err(err, "extract")
            size = os.path.getsize(out_path)
            if size > max_size:
                raise CabError(f"member exceeds max_size: {size} > {max_size}")
            with open(out_path, "rb") as f:
                return f.read()

    def extract(self, name: str, dest_dir: str, *, safe: bool = True) -> str:
        """Extract a member to disk and return the output path.

        Parameters
        ----------
        name:
            Member name within the CAB.
        dest_dir:
            Destination directory to write into.
        safe:
            If True (default), reject absolute paths and path traversal.
        """
        if safe:
            out_path = _safe_join(dest_dir, name)
        else:
            out_path = _unsafe_join(dest_dir, name)
        _ensure_parent(out_path)
        if self._data is not None:
            err = _cab.extract_file_bytes(self._data, name, out_path)
        else:
            err = _cab.extract_file(self.path, name, out_path)
        _raise_for_err(err, "extract")
        return out_path

    def extract_raw(self, name: str, dest_dir: str) -> str:
        """Extract a member using the raw path (no safety checks)."""
        return self.extract(name, dest_dir, safe=False)

    def extract_all(self, dest_dir: str, *, safe: bool = True) -> list[str]:
        """Extract all members to disk and return output paths."""
        paths = []
        for info in self.files():
            name = info.get("name")
            if not isinstance(name, str):
                continue
            paths.append(self.extract(name, dest_dir, safe=safe))
        return paths

    def extract_all_raw(self, dest_dir: str) -> list[str]:
        """Extract all members using raw paths (no safety checks)."""
        return self.extract_all(dest_dir, safe=False)
