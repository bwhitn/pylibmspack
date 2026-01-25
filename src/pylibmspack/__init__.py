"""In-process libmspack bindings for CAB, CHM, and SZDD files."""

from __future__ import annotations

from . import _libmspack as _libmspack  # noqa: F401
from .cab import CabArchive, CabFileInfo, CabInfo
from .chm import ChmArchive, ChmFileInfo, ChmInfo
from .errors import (
    CabDecompressionError,
    CabError,
    CabFormatError,
    CabPathTraversalError,
    ChmDecompressionError,
    ChmError,
    ChmFormatError,
    ChmPathTraversalError,
    MspackDecompressionError,
    MspackError,
    MspackFormatError,
    MspackPathTraversalError,
    SzddDecompressionError,
    SzddError,
    SzddFormatError,
    SzddPathTraversalError,
)
from .szdd import SzddFile, SzddInfo

__all__ = [
    "CabArchive",
    "CabFileInfo",
    "CabInfo",
    "ChmArchive",
    "ChmFileInfo",
    "ChmInfo",
    "SzddFile",
    "SzddInfo",
    "MspackError",
    "MspackFormatError",
    "MspackDecompressionError",
    "MspackPathTraversalError",
    "CabError",
    "CabFormatError",
    "CabDecompressionError",
    "CabPathTraversalError",
    "ChmError",
    "ChmFormatError",
    "ChmDecompressionError",
    "ChmPathTraversalError",
    "SzddError",
    "SzddFormatError",
    "SzddDecompressionError",
    "SzddPathTraversalError",
]

__version__ = "0.1.0"
