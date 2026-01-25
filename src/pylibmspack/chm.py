from __future__ import annotations

import os
import tempfile
from typing import Optional, TypedDict

from . import _cab
from ._paths import ensure_parent, safe_join, unsafe_join
from .errors import (
    ChmDecompressionError,
    ChmError,
    ChmFormatError,
    ChmPathTraversalError,
)


_ERR_OK = getattr(_cab, "MSPACK_ERR_OK", 0)
_ERR_DATAFORMAT = getattr(_cab, "MSPACK_ERR_DATAFORMAT", -1)
_ERR_DECRUNCH = getattr(_cab, "MSPACK_ERR_DECRUNCH", -1)
_ERR_BADCOMP = getattr(_cab, "MSPACK_ERR_BADCOMP", -1)
_ERR_SIGNATURE = getattr(_cab, "MSPACK_ERR_SIGNATURE", -1)
_ERR_CHECKSUM = getattr(_cab, "MSPACK_ERR_CHECKSUM", -1)
_ERR_READ = getattr(_cab, "MSPACK_ERR_READ", -1)


def _raise_for_err(err: int, context: str) -> None:
    if err == _ERR_OK:
        return
    if err in {_ERR_DATAFORMAT, _ERR_BADCOMP, _ERR_SIGNATURE, _ERR_CHECKSUM, _ERR_READ}:
        raise ChmFormatError(f"{context} failed: libmspack error {err}")
    if err == _ERR_DECRUNCH:
        raise ChmDecompressionError(f"{context} failed: libmspack error {err}")
    raise ChmError(f"{context} failed: libmspack error {err}")


def _safe_join(dest_dir: str, name: str) -> str:
    try:
        return safe_join(dest_dir, name)
    except ValueError as exc:
        raise ChmPathTraversalError(str(exc)) from exc


def _unsafe_join(dest_dir: str, name: str) -> str:
    return unsafe_join(dest_dir, name)


def _ensure_parent(path: str) -> None:
    ensure_parent(path)


def _normalize_chm_name(name: str) -> str:
    # CHM members frequently start with a leading '/' that is not an absolute path.
    return name.lstrip("/")


class ChmFileInfo(TypedDict):
    """Typed metadata for a CHM member."""

    name: str
    size: int
    offset: int
    section_id: int
    section: str
    is_system: bool


class ChmInfo(TypedDict):
    """Typed metadata for a CHM header."""

    filename: Optional[str]
    length: int
    version: int
    timestamp: int
    language: int
    dir_offset: int
    num_chunks: int
    chunk_size: int
    density: int
    depth: int
    index_root: int
    first_pmgl: int
    last_pmgl: int
    files_count: int
    sysfiles_count: int


class ChmArchive:
    """Read and extract files from a CHM archive.

    Parameters
    ----------
    path:
        Path to a CHM file on disk.
    """

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None

    @classmethod
    def from_bytes(cls, data: bytes) -> "ChmArchive":
        """Create an archive backed by an in-memory CHM buffer."""
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        return obj

    def files(self, *, include_system: bool = True) -> list[ChmFileInfo]:
        """Return metadata for each member in the CHM.

        Parameters
        ----------
        include_system:
            Include system (\"::\") entries when True.
        """
        if self._data is not None:
            files, err = _cab.chm_list_files_bytes(self._data)
        else:
            files, err = _cab.chm_list_files(self.path)
        _raise_for_err(err, "listing")
        if files is None:
            return []
        if include_system:
            return files
        return [entry for entry in files if not entry.get("is_system")]

    def info(self) -> ChmInfo:
        """Return parsed CHM header information."""
        if self._data is not None:
            info, err = _cab.chm_info_bytes(self._data)
        else:
            info, err = _cab.chm_info(self.path)
        _raise_for_err(err, "info")
        if info is None:
            raise ChmError("info failed: no data")
        return info

    def read(self, name: str, *, max_size: int = 256 * 1024 * 1024) -> bytes:
        """Extract a member and return its bytes.

        Parameters
        ----------
        name:
            Member name within the CHM.
        max_size:
            Maximum allowed size in bytes. Defaults to 256 MiB.
        """
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        member = _normalize_chm_name(name)
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_path = _safe_join(tmp, member)
            _ensure_parent(out_path)
            if self._data is not None:
                err = _cab.chm_extract_file_bytes(self._data, name, out_path)
            else:
                err = _cab.chm_extract_file(self.path, name, out_path)
            _raise_for_err(err, "extract")
            size = os.path.getsize(out_path)
            if size > max_size:
                raise ChmError(f"member exceeds max_size ({size} > {max_size})")
            with open(out_path, "rb") as f:
                return f.read()

    def extract(self, name: str, dest_dir: str, *, safe: bool = True) -> str:
        """Extract a member to disk and return the output path."""
        member = _normalize_chm_name(name)
        out_path = _safe_join(dest_dir, member) if safe else _unsafe_join(dest_dir, member)
        _ensure_parent(out_path)
        if self._data is not None:
            err = _cab.chm_extract_file_bytes(self._data, name, out_path)
        else:
            err = _cab.chm_extract_file(self.path, name, out_path)
        _raise_for_err(err, "extract")
        return out_path

    def extract_all(self, dest_dir: str, *, safe: bool = True, include_system: bool = True) -> list[str]:
        """Extract all members to disk and return output paths."""
        out_paths: list[str] = []
        for info in self.files(include_system=include_system):
            out_paths.append(self.extract(info["name"], dest_dir, safe=safe))
        return out_paths

    def extract_raw(self, name: str, dest_dir: str) -> str:
        """Extract a member using raw (unsafe) path handling."""
        return self.extract(name, dest_dir, safe=False)

    def extract_all_raw(self, dest_dir: str, *, include_system: bool = True) -> list[str]:
        """Extract all members using raw (unsafe) path handling."""
        return self.extract_all(dest_dir, safe=False, include_system=include_system)
