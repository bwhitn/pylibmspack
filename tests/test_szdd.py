from pathlib import Path

import pytest

from pylibmspack import SzddError, SzddFile, SzddFormatError


FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPECTED = FIXTURES / "expected"


def test_szdd_info_and_read(tmp_path):
    szdd = SzddFile(str(FIXTURES / "sample.tx_"))
    info = szdd.info()
    assert info["format"] in {"normal", "qbasic", "unknown"}
    assert info["length"] > 0
    assert info["suggested_name"] == "sample.txt"
    assert 0 <= info["missing_char"] <= 255

    data = szdd.read()
    assert data == (EXPECTED / "szdd.txt").read_bytes()

    out_path = szdd.extract(str(tmp_path))
    assert Path(out_path).read_bytes() == (EXPECTED / "szdd.txt").read_bytes()


def test_szdd_from_bytes():
    data = (FIXTURES / "sample.tx_").read_bytes()
    szdd = SzddFile.from_bytes(data, name="sample.tx_")
    info = szdd.info()
    assert info["suggested_name"] == "sample.txt"
    assert szdd.read() == (EXPECTED / "szdd.txt").read_bytes()


def test_szdd_invalid_bytes():
    szdd = SzddFile.from_bytes(b"not a szdd", name="bad.sz_")
    with pytest.raises(SzddFormatError):
        szdd.info()


def test_szdd_max_size():
    szdd = SzddFile(str(FIXTURES / "sample.tx_"))
    with pytest.raises(SzddError):
        szdd.read(max_size=1)
