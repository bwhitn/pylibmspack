"""In-process libmspack bindings for Microsoft CAB files."""

from __future__ import annotations

from . import _libmspack as _libmspack  # noqa: F401
from .cab import CabArchive, CabFileInfo, CabInfo
from .errors import (
    CabDecompressionError,
    CabError,
    CabFormatError,
    CabPathTraversalError,
)

__all__ = [
    "CabArchive",
    "CabFileInfo",
    "CabInfo",
    "CabError",
    "CabFormatError",
    "CabDecompressionError",
    "CabPathTraversalError",
]

__version__ = "0.1.0"
