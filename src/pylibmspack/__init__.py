"""In-process libmspack bindings for CAB, CHM, and SZDD files."""

from __future__ import annotations

from . import _libmspack as _libmspack  # noqa: F401
from .cab import CabArchive, CabFileInfo, CabInfo
from .chm import ChmArchive, ChmFileInfo, ChmInfo
from .kwaj import KwajFile, KwajInfo
from .errors import (
    CabDecompressionError,
    CabError,
    CabFormatError,
    CabPathTraversalError,
    ChmDecompressionError,
    ChmError,
    ChmFormatError,
    ChmPathTraversalError,
    KwajDecompressionError,
    KwajError,
    KwajFormatError,
    KwajPathTraversalError,
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
    "KwajFile",
    "KwajInfo",
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
    "KwajError",
    "KwajFormatError",
    "KwajDecompressionError",
    "KwajPathTraversalError",
]

__version__ = "0.2.0"
