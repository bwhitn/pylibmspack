from pathlib import Path

import pytest

from pylibmspack import OabError, OabFile, OabFormatError, OabPatch, OabPathTraversalError


def _le32(value: int) -> bytes:
    return value.to_bytes(4, "little")


def _full_oab(payload: bytes) -> bytes:
    block_max = max(len(payload), 1)
    header = _le32(3) + _le32(1) + _le32(block_max) + _le32(len(payload))
    block = _le32(0) + _le32(len(payload)) + _le32(len(payload)) + _le32(0)
    return header + block + payload


def test_oab_read_and_extract(tmp_path):
    payload = b"OAB payload"
    path = tmp_path / "full-download.lzx"
    path.write_bytes(_full_oab(payload))

    oab = OabFile(str(path))

    assert oab.suggested_name() == "full-download.oab"
    assert oab.read() == payload
    out_path = oab.extract(str(tmp_path / "out"), out_name="address-book.oab")
    assert Path(out_path).read_bytes() == payload


def test_oab_from_bytes():
    payload = b"from memory"

    oab = OabFile.from_bytes(_full_oab(payload), name="sample.lzx")

    assert oab.suggested_name() == "sample.oab"
    assert oab.read() == payload


def test_oab_invalid_bytes():
    oab = OabFile.from_bytes(b"not an oab", name="bad.lzx")

    with pytest.raises(OabFormatError):
        oab.read()


def test_oab_max_size():
    oab = OabFile.from_bytes(_full_oab(b"too large"))

    with pytest.raises(OabError):
        oab.read(max_size=1)


def test_oab_invalid_decompbuf():
    oab = OabFile.from_bytes(_full_oab(b"payload"))

    with pytest.raises(ValueError, match="decompbuf"):
        oab.read(decompbuf=15)


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "..\\evil.txt",
        "/../evil.txt",
        "C:\\evil.txt",
        "\\\\server\\share\\evil.txt",
    ],
)
def test_oab_safe_extract_blocks_traversal(tmp_path, name):
    oab = OabFile.from_bytes(_full_oab(b"payload"))

    with pytest.raises(OabPathTraversalError):
        oab.extract(str(tmp_path), out_name=name, safe=True)


def test_oab_patch_invalid_bytes():
    patch = OabPatch.from_bytes(b"not a patch")

    with pytest.raises(OabFormatError):
        patch.read(b"base data")


def test_oab_patch_safe_apply_blocks_traversal(tmp_path):
    patch = OabPatch.from_bytes(b"not a patch")

    with pytest.raises(OabPathTraversalError):
        patch.apply(b"base data", str(tmp_path), out_name="../evil.oab")
