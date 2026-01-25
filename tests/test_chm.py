from pathlib import Path

import pytest

from pylibmspack import (
    ChmArchive,
    ChmError,
    ChmFormatError,
    ChmPathTraversalError,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_CHM = FIXTURES / "sample.chm"

if not SAMPLE_CHM.exists():
    pytest.skip("sample.chm fixture not available", allow_module_level=True)


def test_chm_list_and_info():
    chm = ChmArchive(str(SAMPLE_CHM))
    info = chm.info()
    for key in [
        "filename",
        "length",
        "version",
        "timestamp",
        "language",
        "dir_offset",
        "num_chunks",
        "chunk_size",
        "density",
        "depth",
        "index_root",
        "first_pmgl",
        "last_pmgl",
        "files_count",
        "sysfiles_count",
    ]:
        assert key in info
    assert info["files_count"] >= 1
    assert info["length"] > 0
    assert info["chunk_size"] > 0
    assert info["num_chunks"] >= 0

    files = chm.files(include_system=False)
    assert files
    entry = files[0]
    assert entry["size"] >= 0
    assert "section" in entry
    assert "section_id" in entry


def test_chm_read_and_extract(tmp_path):
    chm = ChmArchive(str(SAMPLE_CHM))
    files = chm.files(include_system=False)
    files = [f for f in files if f["size"] > 0]
    smallest = min(files, key=lambda f: f["size"])
    data = chm.read(smallest["name"], max_size=smallest["size"])
    assert len(data) == smallest["size"]

    out_path = chm.extract(smallest["name"], str(tmp_path))
    assert Path(out_path).read_bytes() == data


def test_chm_from_bytes():
    data = SAMPLE_CHM.read_bytes()
    chm = ChmArchive.from_bytes(data)
    files = chm.files(include_system=False)
    files = [f for f in files if f["size"] > 0]
    smallest = min(files, key=lambda f: f["size"])
    payload = chm.read(smallest["name"], max_size=smallest["size"])
    assert len(payload) == smallest["size"]


def test_chm_invalid_bytes():
    chm = ChmArchive.from_bytes(b"not a chm")
    with pytest.raises(ChmFormatError):
        chm.info()


def test_chm_missing_member():
    chm = ChmArchive(str(SAMPLE_CHM))
    with pytest.raises(ChmError):
        chm.read("no_such_member.txt")


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
def test_chm_safe_extract_blocks_traversal(tmp_path, name):
    chm = ChmArchive(str(SAMPLE_CHM))
    with pytest.raises(ChmPathTraversalError):
        chm.extract(name, str(tmp_path), safe=True)
