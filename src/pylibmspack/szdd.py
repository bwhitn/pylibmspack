from __future__ import annotations

import os
import tempfile
from typing import Optional, TypedDict

from . import _cab
from ._paths import ensure_parent, safe_join, unsafe_join
from .errors import (
    SzddDecompressionError,
    SzddError,
    SzddFormatError,
    SzddPathTraversalError,
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
        raise SzddFormatError(f"{context} failed: libmspack error {err}")
    if err == _ERR_DECRUNCH:
        raise SzddDecompressionError(f"{context} failed: libmspack error {err}")
    raise SzddError(f"{context} failed: libmspack error {err}")


def _safe_join(dest_dir: str, name: str) -> str:
    try:
        return safe_join(dest_dir, name)
    except ValueError as exc:
        raise SzddPathTraversalError(str(exc)) from exc


def _unsafe_join(dest_dir: str, name: str) -> str:
    return unsafe_join(dest_dir, name)


def _ensure_parent(path: str) -> None:
    ensure_parent(path)


def _missing_char_str(value: int) -> str:
    if value == 0:
        return ""
    return bytes([value]).decode("latin-1", "strict")


def _apply_missing_char(name: str, missing: int) -> str:
    if not name:
        return name
    if missing == 0:
        return name
    ch = _missing_char_str(missing)
    if not ch:
        return name
    if name.endswith("_") or name.endswith("$"):
        return name[:-1] + ch
    return name[:-1] + ch


class SzddInfo(TypedDict):
    """Typed metadata for a SZDD header."""

    format_id: int
    format: str
    length: int
    missing_char: int
    missing_char_str: str
    suggested_name: str


class SzddFile:
    """Read and extract data from a SZDD-compressed file.

    Parameters
    ----------
    path:
        Path to a SZDD file on disk.
    """

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None
        self._name_override: Optional[str] = None

    @classmethod
    def from_bytes(cls, data: bytes, *, name: str = "memory.sz_") -> "SzddFile":
        """Create a SZDD reader backed by in-memory bytes."""
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        obj._name_override = name
        return obj

    def info(self) -> SzddInfo:
        """Return parsed SZDD header information."""
        if self._data is not None:
            info, err = _cab.szdd_info_bytes(self._data)
        else:
            info, err = _cab.szdd_info(self.path)
        _raise_for_err(err, "info")
        if info is None:
            raise SzddError("info failed: no data")
        missing = int(info.get("missing_char", 0))
        base_name = self._name_override or os.path.basename(self.path)
        suggested = _apply_missing_char(base_name, missing)
        info["missing_char_str"] = _missing_char_str(missing)
        info["suggested_name"] = suggested
        return info

    def suggested_name(self) -> str:
        """Return the default output filename based on the SZDD header."""
        return self.info()["suggested_name"]

    def read(self, *, max_size: int = 256 * 1024 * 1024) -> bytes:
        """Decompress and return file contents."""
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_name = self.suggested_name()
            if not out_name:
                out_name = "output"
            out_path = _safe_join(tmp, out_name)
            _ensure_parent(out_path)
            if self._data is not None:
                err = _cab.szdd_extract_bytes(self._data, out_path)
            else:
                err = _cab.szdd_extract(self.path, out_path)
            _raise_for_err(err, "extract")
            size = os.path.getsize(out_path)
            if size > max_size:
                raise SzddError(f"file exceeds max_size ({size} > {max_size})")
            with open(out_path, "rb") as f:
                return f.read()

    def extract(
        self,
        dest_dir: str,
        *,
        safe: bool = True,
        out_name: Optional[str] = None,
    ) -> str:
        """Decompress to disk and return the output path."""
        name = out_name or self.suggested_name()
        if not name:
            raise SzddError("output name is required")
        out_path = _safe_join(dest_dir, name) if safe else _unsafe_join(dest_dir, name)
        _ensure_parent(out_path)
        if self._data is not None:
            err = _cab.szdd_extract_bytes(self._data, out_path)
        else:
            err = _cab.szdd_extract(self.path, out_path)
        _raise_for_err(err, "extract")
        return out_path

    def extract_raw(self, dest_dir: str, *, out_name: Optional[str] = None) -> str:
        """Decompress using raw (unsafe) path handling."""
        return self.extract(dest_dir, safe=False, out_name=out_name)
