class MspackError(Exception):
    """Base error for libmspack handling."""


class MspackFormatError(MspackError):
    """File is corrupt, truncated, or uses unsupported features."""


class MspackDecompressionError(MspackError):
    """File could not be decompressed."""


class MspackPathTraversalError(MspackError):
    """Unsafe path detected during extraction."""


class CabError(MspackError):
    """Base error for CAB handling."""


class CabFormatError(CabError, MspackFormatError):
    """CAB file is corrupt, truncated, or uses unsupported features."""


class CabDecompressionError(CabError, MspackDecompressionError):
    """CAB file could not be decompressed."""


class CabPathTraversalError(CabError, MspackPathTraversalError):
    """Unsafe path detected during extraction."""


class ChmError(MspackError):
    """Base error for CHM handling."""


class ChmFormatError(ChmError, MspackFormatError):
    """CHM file is corrupt, truncated, or uses unsupported features."""


class ChmDecompressionError(ChmError, MspackDecompressionError):
    """CHM file could not be decompressed."""


class ChmPathTraversalError(ChmError, MspackPathTraversalError):
    """Unsafe path detected during extraction."""


class SzddError(MspackError):
    """Base error for SZDD handling."""


class SzddFormatError(SzddError, MspackFormatError):
    """SZDD file is corrupt, truncated, or uses unsupported features."""


class SzddDecompressionError(SzddError, MspackDecompressionError):
    """SZDD file could not be decompressed."""


class SzddPathTraversalError(SzddError, MspackPathTraversalError):
    """Unsafe path detected during extraction."""


class KwajError(MspackError):
    """Base error for KWAJ handling."""


class KwajFormatError(KwajError, MspackFormatError):
    """KWAJ file is corrupt, truncated, or uses unsupported features."""


class KwajDecompressionError(KwajError, MspackDecompressionError):
    """KWAJ file could not be decompressed."""


class KwajPathTraversalError(KwajError, MspackPathTraversalError):
    """Unsafe path detected during extraction."""
