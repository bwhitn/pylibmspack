import os
from pathlib import Path

import pytest

from pymspack import CabArchive, CabPathTraversalError

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_files():
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    files = cab.files()
    assert len(files) == 2
    for entry in files:
        for key in [
            "name",
            "size",
            "dos_date",
            "dos_time",
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
    assert sizes["hello.txt"] == 6
    assert sizes["world.txt"] == 6


def test_read_member():
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    assert cab.read("hello.txt") == b"hello\n"
    assert cab.read("world.txt") == b"world\n"


def test_safe_extract_blocks_traversal(tmp_path):
    cab = CabArchive(str(FIXTURES / "traversal.cab"))
    with pytest.raises(CabPathTraversalError):
        cab.extract("../evil.txt", str(tmp_path))


def test_extract_all(tmp_path):
    cab = CabArchive(str(FIXTURES / "small_mszip.cab"))
    out_paths = cab.extract_all(str(tmp_path))
    assert len(out_paths) == 2
    assert (tmp_path / "hello.txt").read_bytes() == b"hello\n"
    assert (tmp_path / "world.txt").read_bytes() == b"world\n"


def test_from_bytes_and_info():
    data = (FIXTURES / "small_mszip.cab").read_bytes()
    cab = CabArchive.from_bytes(data)
    assert cab.read("hello.txt") == b"hello\n"
    info = cab.info()
    assert info["files_count"] == 2
