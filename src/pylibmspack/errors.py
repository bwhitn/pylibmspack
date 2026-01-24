class CabError(Exception):
    """Base error for CAB handling.

    All pylibmspack exceptions derive from this type.
    """


class CabFormatError(CabError):
    """CAB file is corrupt, truncated, or uses unsupported features."""


class CabDecompressionError(CabError):
    """CAB file could not be decompressed."""


class CabPathTraversalError(CabError):
    """Unsafe path detected during extraction."""
