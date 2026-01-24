import os
from pathlib import Path

import pytest

from pylibmspack import CabArchive, CabPathTraversalError

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = FIXTURES / "expected"

def _norm_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def test_list_files():
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    files = cab.files()
    assert len(files) == 3
    for entry in files:
        for key in [
            "name",
            "size",
            "dos_date",
            "dos_time",
            "date_y",
            "date_m",
            "date_d",
            "time_h",
            "time_m",
            "time_s",
            "datetime_utc",
            "attrs",
            "is_readonly",
            "is_hidden",
            "is_system",
            "is_archive",
            "folder_index",
            "offset",
            "compression",
            "has_prev",
            "has_next",
            "prev_cabinet",
            "next_cabinet",
            "cabinet_set_id",
            "cabinet_set_index",
        ]:
            assert key in entry
    sizes = {e["name"]: e["size"] for e in files}
    assert sizes["mszip.txt"] == len(_norm_newlines((EXPECTED / "mszip.txt").read_bytes()))
    assert sizes["lzx.txt"] == len(_norm_newlines((EXPECTED / "lzx.txt").read_bytes()))
    assert sizes["qtm.txt"] == len(_norm_newlines((EXPECTED / "qtm.txt").read_bytes()))


def test_read_member():
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    assert _norm_newlines(cab.read("mszip.txt")) == _norm_newlines((EXPECTED / "mszip.txt").read_bytes())
    assert _norm_newlines(cab.read("lzx.txt")) == _norm_newlines((EXPECTED / "lzx.txt").read_bytes())
    assert _norm_newlines(cab.read("qtm.txt")) == _norm_newlines((EXPECTED / "qtm.txt").read_bytes())


def test_safe_extract_blocks_traversal(tmp_path):
    cab = CabArchive(str(FIXTURES / "traversal.cab"))
    with pytest.raises(CabPathTraversalError):
        cab.extract("..\\\\..\\\\a", str(tmp_path))


def test_extract_all(tmp_path):
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    out_paths = cab.extract_all(str(tmp_path))
    assert len(out_paths) == 3
    assert _norm_newlines((tmp_path / "mszip.txt").read_bytes()) == _norm_newlines((EXPECTED / "mszip.txt").read_bytes())
    assert _norm_newlines((tmp_path / "lzx.txt").read_bytes()) == _norm_newlines((EXPECTED / "lzx.txt").read_bytes())
    assert _norm_newlines((tmp_path / "qtm.txt").read_bytes()) == _norm_newlines((EXPECTED / "qtm.txt").read_bytes())


def test_from_bytes_and_info():
    data = (FIXTURES / "small_mszip.cab").read_bytes()
    cab = CabArchive.from_bytes(data)
    assert _norm_newlines(cab.read("mszip.txt")) == _norm_newlines((EXPECTED / "mszip.txt").read_bytes())
    info = cab.info()
    assert info["files_count"] == 3
    files = cab.files()
    assert files[0]["datetime_utc"]
