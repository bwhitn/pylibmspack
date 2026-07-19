from __future__ import annotations

import os
import tempfile
from typing import Optional

from . import _cab
from ._paths import (
    ensure_parent,
    ensure_safe_output_path,
    remove_partial_output,
    safe_join,
    unsafe_join,
)
from .errors import HlpDecompressionError, HlpError, HlpFormatError, HlpPathTraversalError

_ERR_OK = getattr(_cab, "MSPACK_ERR_OK", 0)
_ERR_DATAFORMAT = getattr(_cab, "MSPACK_ERR_DATAFORMAT", -1)
_ERR_DECRUNCH = getattr(_cab, "MSPACK_ERR_DECRUNCH", -1)
_ERR_BADCOMP = getattr(_cab, "MSPACK_ERR_BADCOMP", -1)
_ERR_SIGNATURE = getattr(_cab, "MSPACK_ERR_SIGNATURE", -1)
_ERR_CHECKSUM = getattr(_cab, "MSPACK_ERR_CHECKSUM", -1)
_ERR_READ = getattr(_cab, "MSPACK_ERR_READ", -1)
_ERR_WRITE = getattr(_cab, "MSPACK_ERR_WRITE", -1)
_ERR_OUTPUT_LIMIT = getattr(_cab, "PYLIBMSPACK_ERR_OUTPUT_LIMIT", -1)
_DEFAULT_MAX_SIZE = 256 * 1024 * 1024
_WINHELP_MAGIC = b"?_\x03\x00"


def _raise_for_err(err: int, context: str) -> None:
    if err == _ERR_OK:
        return
    if err in {
        _ERR_DATAFORMAT,
        _ERR_BADCOMP,
        _ERR_SIGNATURE,
        _ERR_CHECKSUM,
        _ERR_READ,
    }:
        raise HlpFormatError(f"{context} failed: libmspack error {err}")
    if err == _ERR_DECRUNCH:
        raise HlpDecompressionError(f"{context} failed: libmspack error {err}")
    if err == _ERR_OUTPUT_LIMIT:
        raise HlpError(f"{context} failed: output exceeds max_size")
    if err == _ERR_WRITE:
        raise HlpError(f"{context} failed: unable to write output")
    raise HlpError(f"{context} failed: libmspack error {err}")


def _safe_join(dest_dir: str, name: str) -> str:
    try:
        return safe_join(dest_dir, name)
    except ValueError as exc:
        raise HlpPathTraversalError(str(exc)) from exc


def _unsafe_join(dest_dir: str, name: str) -> str:
    return unsafe_join(dest_dir, name)


def _ensure_parent(path: str) -> None:
    ensure_parent(path)


def _ensure_safe_output(dest_dir: str, path: str) -> None:
    try:
        ensure_safe_output_path(dest_dir, path)
    except ValueError as exc:
        raise HlpPathTraversalError(str(exc)) from exc


def _check_not_winhelp_container(data: bytes) -> None:
    if data.startswith(_WINHELP_MAGIC):
        raise HlpFormatError("full WinHelp .hlp containers are not supported by bundled libmspack")


class HlpFile:
    """Decompress Microsoft Help LZSS streams.

    The bundled libmspack source does not implement the full WinHelp .hlp
    container parser. This class handles the MS Help-flavored LZSS stream used
    inside those files.
    """

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None
        self._name_override: Optional[str] = None

    @classmethod
    def from_bytes(cls, data: bytes, *, name: str = "memory.hlp") -> "HlpFile":
        """Create an HLP LZSS reader backed by in-memory bytes."""
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        obj._name_override = name
        return obj

    def suggested_name(self) -> str:
        """Return the default output filename."""
        if self._name_override:
            return os.path.basename(self._name_override)
        if self.path != "<memory>":
            return os.path.basename(self.path)
        return "output"

    def _check_supported_input(self) -> None:
        if self._data is not None:
            _check_not_winhelp_container(self._data[:4])
            return
        with open(self.path, "rb") as f:
            _check_not_winhelp_container(f.read(4))

    def read(self, *, max_size: int = _DEFAULT_MAX_SIZE) -> bytes:
        """Decompress and return stream contents."""
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._check_supported_input()
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_path = _safe_join(tmp, self.suggested_name() or "output")
            _ensure_parent(out_path)
            if self._data is not None:
                err = _cab.hlp_decompress_bytes(self._data, out_path, max_size)
            else:
                err = _cab.hlp_decompress(self.path, out_path, max_size)
            _raise_for_err(err, "decompress")
            size = os.path.getsize(out_path)
            if size > max_size:
                raise HlpError(f"stream exceeds max_size ({size} > {max_size})")
            with open(out_path, "rb") as f:
                return f.read()

    def extract(
        self,
        dest_dir: str,
        *,
        safe: bool = True,
        out_name: Optional[str] = None,
        max_size: int = _DEFAULT_MAX_SIZE,
    ) -> str:
        """Decompress to disk and return the output path."""
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._check_supported_input()
        name = out_name or self.suggested_name()
        if not name:
            raise HlpError("output name is required")
        out_path = _safe_join(dest_dir, name) if safe else _unsafe_join(dest_dir, name)
        _ensure_parent(out_path)
        if safe:
            _ensure_safe_output(dest_dir, out_path)
        if self._data is not None:
            err = _cab.hlp_decompress_bytes(self._data, out_path, max_size)
        else:
            err = _cab.hlp_decompress(self.path, out_path, max_size)
        try:
            _raise_for_err(err, "decompress")
        except Exception:
            if safe:
                remove_partial_output(out_path)
            raise
        return out_path

    def extract_raw(
        self,
        dest_dir: str,
        *,
        out_name: Optional[str] = None,
        max_size: int = _DEFAULT_MAX_SIZE,
    ) -> str:
        """Decompress using raw (unsafe) path handling."""
        return self.extract(dest_dir, safe=False, out_name=out_name, max_size=max_size)
