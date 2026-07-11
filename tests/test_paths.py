from pathlib import Path

import pytest

from pylibmspack._paths import normalize_member_path, safe_join, unsafe_join


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("file.txt", "file.txt"),
        ("folder\\file.txt", "folder/file.txt"),
        ("folder/./file.txt", "folder/file.txt"),
        ("folder//nested/../file.txt", "folder/file.txt"),
    ],
)
def test_normalize_member_path_accepts_safe_relative_paths(raw, normalized):
    assert normalize_member_path(raw) == normalized


@pytest.mark.parametrize(
    "raw",
    [
        "",
        ".",
        "../evil.txt",
        "nested/../../evil.txt",
        "/absolute.txt",
        "C:\\absolute.txt",
        "\\\\server\\share\\evil.txt",
        "bad\x00name.txt",
    ],
)
def test_normalize_member_path_rejects_unsafe_paths(raw):
    with pytest.raises(ValueError):
        normalize_member_path(raw)


def test_safe_join_returns_path_under_destination(tmp_path):
    dest_dir = tmp_path / "out"

    target = safe_join(str(dest_dir), "folder\\file.txt")

    assert Path(target) == dest_dir.resolve() / "folder" / "file.txt"


@pytest.mark.parametrize("raw", ["../evil.txt", "/absolute.txt", "C:\\absolute.txt"])
def test_safe_join_rejects_paths_outside_destination(tmp_path, raw):
    with pytest.raises(ValueError):
        safe_join(str(tmp_path), raw)


def test_unsafe_join_preserves_raw_parent_segments(tmp_path):
    target = unsafe_join(str(tmp_path / "a" / "b"), "..\\file.txt")

    assert Path(target) == tmp_path / "a" / "b" / ".." / "file.txt"
