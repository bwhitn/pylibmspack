from pathlib import Path

import pytest

from pylibmspack import KwajFile, KwajFormatError, KwajPathTraversalError


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_kwaj_info_and_read(tmp_path):
    kwj = KwajFile(str(FIXTURES / "sample.kwj"))
    info = kwj.info()
    assert "compression" in info
    assert info["data_offset"] >= 0
    assert info["headers"] >= 0
    assert info["extra_length"] >= 0

    data = kwj.read()
    out_path = kwj.extract(str(tmp_path))
    assert Path(out_path).read_bytes() == data


def test_kwaj_from_bytes():
    data = (FIXTURES / "sample.kwj").read_bytes()
    kwj = KwajFile.from_bytes(data, name="sample.kwj")
    assert kwj.read()


def test_kwaj_invalid_bytes():
    kwj = KwajFile.from_bytes(b"not a kwaj", name="bad.kwj")
    with pytest.raises(KwajFormatError):
        kwj.info()


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
def test_kwaj_safe_extract_blocks_traversal(tmp_path, name):
    kwj = KwajFile(str(FIXTURES / "sample.kwj"))
    with pytest.raises(KwajPathTraversalError):
        kwj.extract(str(tmp_path), out_name=name, safe=True)
