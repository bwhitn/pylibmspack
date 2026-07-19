"""In-process libmspack bindings for Microsoft compression formats."""

from __future__ import annotations

from . import _libmspack as _libmspack
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
    HlpDecompressionError,
    HlpError,
    HlpFormatError,
    HlpPathTraversalError,
    KwajDecompressionError,
    KwajError,
    KwajFormatError,
    KwajPathTraversalError,
    MspackDecompressionError,
    MspackError,
    MspackFormatError,
    MspackPathTraversalError,
    OabDecompressionError,
    OabError,
    OabFormatError,
    OabPathTraversalError,
    SzddDecompressionError,
    SzddError,
    SzddFormatError,
    SzddPathTraversalError,
)
from .hlp import HlpFile
from .kwaj import KwajFile, KwajInfo
from .oab import OabFile, OabPatch
from .szdd import SzddFile, SzddInfo

__all__ = [
    "CabArchive",
    "CabDecompressionError",
    "CabError",
    "CabFileInfo",
    "CabFormatError",
    "CabInfo",
    "CabPathTraversalError",
    "ChmArchive",
    "ChmDecompressionError",
    "ChmError",
    "ChmFileInfo",
    "ChmFormatError",
    "ChmInfo",
    "ChmPathTraversalError",
    "HlpDecompressionError",
    "HlpError",
    "HlpFile",
    "HlpFormatError",
    "HlpPathTraversalError",
    "KwajDecompressionError",
    "KwajError",
    "KwajFile",
    "KwajFormatError",
    "KwajInfo",
    "KwajPathTraversalError",
    "MspackDecompressionError",
    "MspackError",
    "MspackFormatError",
    "MspackPathTraversalError",
    "OabDecompressionError",
    "OabError",
    "OabFile",
    "OabFormatError",
    "OabPatch",
    "OabPathTraversalError",
    "SzddDecompressionError",
    "SzddError",
    "SzddFile",
    "SzddFormatError",
    "SzddInfo",
    "SzddPathTraversalError",
]

__version__ = "0.4.0"
