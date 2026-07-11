from __future__ import annotations

import os
import tempfile
from typing import Optional, Union

from . import _cab
from ._paths import ensure_parent, safe_join, unsafe_join
from .errors import OabDecompressionError, OabError, OabFormatError, OabPathTraversalError

_ERR_OK = getattr(_cab, "MSPACK_ERR_OK", 0)
_ERR_DATAFORMAT = getattr(_cab, "MSPACK_ERR_DATAFORMAT", -1)
_ERR_DECRUNCH = getattr(_cab, "MSPACK_ERR_DECRUNCH", -1)
_ERR_BADCOMP = getattr(_cab, "MSPACK_ERR_BADCOMP", -1)
_ERR_SIGNATURE = getattr(_cab, "MSPACK_ERR_SIGNATURE", -1)
_ERR_CHECKSUM = getattr(_cab, "MSPACK_ERR_CHECKSUM", -1)
_ERR_READ = getattr(_cab, "MSPACK_ERR_READ", -1)
_ERR_WRITE = getattr(_cab, "MSPACK_ERR_WRITE", -1)
_ERR_ARGS = getattr(_cab, "MSPACK_ERR_ARGS", -1)


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
        raise OabFormatError(f"{context} failed: libmspack error {err}")
    if err == _ERR_DECRUNCH:
        raise OabDecompressionError(f"{context} failed: libmspack error {err}")
    if err == _ERR_WRITE:
        raise OabError(f"{context} failed: unable to write output")
    if err == _ERR_ARGS:
        raise ValueError(f"{context} failed: invalid argument")
    raise OabError(f"{context} failed: libmspack error {err}")


def _safe_join(dest_dir: str, name: str) -> str:
    try:
        return safe_join(dest_dir, name)
    except ValueError as exc:
        raise OabPathTraversalError(str(exc)) from exc


def _unsafe_join(dest_dir: str, name: str) -> str:
    return unsafe_join(dest_dir, name)


def _ensure_parent(path: str) -> None:
    ensure_parent(path)


def _default_output_name(name: str) -> str:
    base = os.path.basename(name)
    root, ext = os.path.splitext(base)
    if ext.lower() == ".lzx" and root:
        return root + ".oab"
    return base or "output.oab"


def _check_decompbuf(value: int) -> None:
    if value < 16:
        raise ValueError("decompbuf must be at least 16 bytes")


class OabFile:
    """Decompress Exchange Offline Address Book .LZX full-download files."""

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None
        self._name_override: Optional[str] = None

    @classmethod
    def from_bytes(cls, data: bytes, *, name: str = "memory.lzx") -> "OabFile":
        """Create an OAB reader backed by in-memory bytes."""
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        obj._name_override = name
        return obj

    def suggested_name(self) -> str:
        """Return the default output filename."""
        if self._name_override:
            return _default_output_name(self._name_override)
        if self.path != "<memory>":
            return _default_output_name(self.path)
        return "output.oab"

    def read(self, *, max_size: int = 256 * 1024 * 1024, decompbuf: int = 4096) -> bytes:
        """Decompress a full OAB .LZX file and return its bytes."""
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        _check_decompbuf(decompbuf)
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_path = _safe_join(tmp, self.suggested_name())
            _ensure_parent(out_path)
            if self._data is not None:
                err = _cab.oab_decompress_bytes(self._data, out_path, decompbuf)
            else:
                err = _cab.oab_decompress(self.path, out_path, decompbuf)
            _raise_for_err(err, "decompress")
            size = os.path.getsize(out_path)
            if size > max_size:
                raise OabError(f"file exceeds max_size ({size} > {max_size})")
            with open(out_path, "rb") as f:
                return f.read()

    def extract(
        self,
        dest_dir: str,
        *,
        safe: bool = True,
        out_name: Optional[str] = None,
        decompbuf: int = 4096,
    ) -> str:
        """Decompress a full OAB .LZX file to disk and return the output path."""
        _check_decompbuf(decompbuf)
        name = out_name or self.suggested_name()
        if not name:
            raise OabError("output name is required")
        out_path = _safe_join(dest_dir, name) if safe else _unsafe_join(dest_dir, name)
        _ensure_parent(out_path)
        if self._data is not None:
            err = _cab.oab_decompress_bytes(self._data, out_path, decompbuf)
        else:
            err = _cab.oab_decompress(self.path, out_path, decompbuf)
        _raise_for_err(err, "decompress")
        return out_path

    def extract_raw(
        self,
        dest_dir: str,
        *,
        out_name: Optional[str] = None,
        decompbuf: int = 4096,
    ) -> str:
        """Decompress using raw (unsafe) path handling."""
        return self.extract(dest_dir, safe=False, out_name=out_name, decompbuf=decompbuf)


class OabPatch:
    """Apply Exchange Offline Address Book .LZX incremental patch files."""

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self._data: Optional[bytes] = None
        self._name_override: Optional[str] = None

    @classmethod
    def from_bytes(cls, data: bytes, *, name: str = "memory.lzx") -> "OabPatch":
        """Create an OAB incremental patch reader backed by in-memory bytes."""
        obj = cls.__new__(cls)
        obj.path = "<memory>"
        obj._data = bytes(data)
        obj._name_override = name
        return obj

    def suggested_name(self) -> str:
        """Return the default output filename."""
        if self._name_override:
            return _default_output_name(self._name_override)
        if self.path != "<memory>":
            return _default_output_name(self.path)
        return "patched.oab"

    def read(
        self,
        base: Union[str, bytes],
        *,
        max_size: int = 256 * 1024 * 1024,
        decompbuf: int = 4096,
    ) -> bytes:
        """Apply this incremental patch to a base OAB and return patched bytes."""
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            out_path = _safe_join(tmp, self.suggested_name())
            _ensure_parent(out_path)
            self._apply_to_path(base, out_path, decompbuf=decompbuf, tmp=tmp)
            size = os.path.getsize(out_path)
            if size > max_size:
                raise OabError(f"file exceeds max_size ({size} > {max_size})")
            with open(out_path, "rb") as f:
                return f.read()

    def apply(
        self,
        base: Union[str, bytes],
        dest_dir: str,
        *,
        safe: bool = True,
        out_name: Optional[str] = None,
        decompbuf: int = 4096,
    ) -> str:
        """Apply this incremental patch to a base OAB on disk."""
        _check_decompbuf(decompbuf)
        name = out_name or self.suggested_name()
        if not name:
            raise OabError("output name is required")
        out_path = _safe_join(dest_dir, name) if safe else _unsafe_join(dest_dir, name)
        _ensure_parent(out_path)
        with tempfile.TemporaryDirectory(prefix="pylibmspack-") as tmp:
            self._apply_to_path(base, out_path, decompbuf=decompbuf, tmp=tmp)
        return out_path

    def apply_raw(
        self,
        base: Union[str, bytes],
        dest_dir: str,
        *,
        out_name: Optional[str] = None,
        decompbuf: int = 4096,
    ) -> str:
        """Apply this patch using raw (unsafe) path handling."""
        return self.apply(base, dest_dir, safe=False, out_name=out_name, decompbuf=decompbuf)

    def _apply_to_path(
        self,
        base: Union[str, bytes],
        out_path: str,
        *,
        decompbuf: int,
        tmp: str,
    ) -> None:
        _check_decompbuf(decompbuf)
        patch_path = self.path
        if self._data is not None:
            patch_path = os.path.join(tmp, "patch.lzx")
            with open(patch_path, "wb") as f:
                f.write(self._data)

        base_path = base
        if isinstance(base, (bytes, bytearray, memoryview)):
            base_path = os.path.join(tmp, "base.oab")
            with open(base_path, "wb") as f:
                f.write(bytes(base))

        err = _cab.oab_decompress_incremental(patch_path, os.fspath(base_path), out_path, decompbuf)
        _raise_for_err(err, "patch")
