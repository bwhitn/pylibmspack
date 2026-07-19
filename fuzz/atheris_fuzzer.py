#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Callable

import atheris

with atheris.instrument_imports():
    from pylibmspack import (
        CabArchive,
        ChmArchive,
        HlpFile,
        KwajFile,
        MspackError,
        OabFile,
        OabPatch,
        SzddFile,
    )

EXPECTED_EXCEPTIONS = (MspackError, OSError, ValueError, EOFError)
TARGETS = ("all", "cab", "chm", "szdd", "kwaj", "hlp", "oab", "oab_patch")
MAX_READ_SIZE = 4096
MAX_LIST_ENTRIES = 4
EXERCISE_DISK = False


def _handled(fn):
    try:
        fn()
    except EXPECTED_EXCEPTIONS:
        return None
    return None


def _max_size(data: bytes) -> int:
    if not data:
        return min(MAX_READ_SIZE, 4096)
    return int.from_bytes(data[:2], "little") % (MAX_READ_SIZE + 1)


def _decompbuf(data: bytes) -> int:
    if not data:
        return 128
    if data[0] & 1:
        return data[0] % 16
    return 16 + (data[0] % 512)


def _member_names(files: list[dict[str, object]]) -> list[str]:
    names = ["", "member.txt", "index.html", "../evil.txt", "C:\\evil.txt"]
    for entry in files[:MAX_LIST_ENTRIES]:
        name = entry.get("name")
        if isinstance(name, str):
            names.append(name)
    return names[: MAX_LIST_ENTRIES + 5]


def _with_disk(data: bytes, suffix: str, fn: Callable[[Path, Path], object]) -> None:
    if not EXERCISE_DISK:
        return
    try:
        with tempfile.TemporaryDirectory(prefix="pylibmspack-atheris-input-") as tmp:
            root = Path(tmp)
            path = root / f"input{suffix}"
            path.write_bytes(data)
            fn(path, root)
    except EXPECTED_EXCEPTIONS:
        return


def fuzz_cab(data: bytes) -> None:
    archive = CabArchive.from_bytes(data)
    files = _handled(archive.files) or []
    _handled(archive.info)
    for name in _member_names(files):
        _handled(lambda name=name: archive.read(name, max_size=_max_size(data)))

    def disk(path: Path, _root: Path) -> None:
        archive = CabArchive(str(path))
        files = _handled(archive.files) or []
        _handled(archive.info)
        for name in _member_names(files):
            _handled(lambda name=name: archive.read(name, max_size=_max_size(data)))

    _with_disk(data, ".cab", disk)


def fuzz_chm(data: bytes) -> None:
    archive = ChmArchive.from_bytes(data)
    files = _handled(archive.files) or []
    _handled(archive.info)
    for name in _member_names(files):
        _handled(lambda name=name: archive.read(name, max_size=_max_size(data)))

    def disk(path: Path, _root: Path) -> None:
        archive = ChmArchive(str(path))
        files = _handled(archive.files) or []
        _handled(archive.info)
        for name in _member_names(files):
            _handled(lambda name=name: archive.read(name, max_size=_max_size(data)))

    _with_disk(data, ".chm", disk)


def fuzz_szdd(data: bytes) -> None:
    reader = SzddFile.from_bytes(data, name="input.tx_")
    _handled(reader.info)
    _handled(lambda: reader.read(max_size=_max_size(data)))

    def disk(path: Path, _root: Path) -> None:
        reader = SzddFile(str(path))
        _handled(reader.info)
        _handled(lambda: reader.read(max_size=_max_size(data)))

    _with_disk(data, ".tx_", disk)


def fuzz_kwaj(data: bytes) -> None:
    reader = KwajFile.from_bytes(data, name="input.kwj")
    _handled(reader.info)
    _handled(lambda: reader.read(max_size=_max_size(data)))

    def disk(path: Path, _root: Path) -> None:
        reader = KwajFile(str(path))
        _handled(reader.info)
        _handled(lambda: reader.read(max_size=_max_size(data)))

    _with_disk(data, ".kwj", disk)


def fuzz_hlp(data: bytes) -> None:
    reader = HlpFile.from_bytes(data, name="input.hlp")
    _handled(lambda: reader.read(max_size=_max_size(data)))

    def disk(path: Path, _root: Path) -> None:
        reader = HlpFile(str(path))
        _handled(lambda: reader.read(max_size=_max_size(data)))

    _with_disk(data, ".hlp", disk)


def fuzz_oab(data: bytes) -> None:
    reader = OabFile.from_bytes(data, name="input.lzx")
    _handled(lambda: reader.read(max_size=_max_size(data), decompbuf=_decompbuf(data)))

    def disk(path: Path, _root: Path) -> None:
        reader = OabFile(str(path))
        _handled(lambda: reader.read(max_size=_max_size(data), decompbuf=_decompbuf(data)))

    _with_disk(data, ".lzx", disk)


def fuzz_oab_patch(data: bytes) -> None:
    splits = {len(data) // 2}
    if data:
        splits.add(data[0] % len(data))
    for split in splits:
        patch = OabPatch.from_bytes(data[:split], name="patch.lzx")
        _handled(
            lambda split=split, patch=patch: patch.read(
                data[split:],
                max_size=_max_size(data),
                decompbuf=_decompbuf(data),
            )
        )

        def disk(path: Path, root: Path, split: int = split) -> None:
            base_path = root / "base.oab"
            base_path.write_bytes(data[split:])
            patch = OabPatch(str(path))
            _handled(
                lambda: patch.read(
                    str(base_path),
                    max_size=_max_size(data),
                    decompbuf=_decompbuf(data),
                )
            )

        _with_disk(data[:split], ".lzx", disk)


TARGET_FUNCS = {
    "cab": fuzz_cab,
    "chm": fuzz_chm,
    "szdd": fuzz_szdd,
    "kwaj": fuzz_kwaj,
    "hlp": fuzz_hlp,
    "oab": fuzz_oab,
    "oab_patch": fuzz_oab_patch,
}


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    if SELECTED_TARGET == "all":
        if not data:
            fuzz_cab(data)
            return
        target = TARGETS[1 + (data[0] % (len(TARGETS) - 1))]
        TARGET_FUNCS[target](data[1:])
        return
    TARGET_FUNCS[SELECTED_TARGET](data)


def parse_args(argv: list[str]) -> tuple[str, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--target", choices=TARGETS, default="all")
    parser.add_argument("--max-read-size", type=int, default=4096)
    parser.add_argument("--max-list-entries", type=int, default=4)
    parser.add_argument("--exercise-disk", action="store_true")
    known, remaining = parser.parse_known_args(argv[1:])
    global EXERCISE_DISK, MAX_LIST_ENTRIES, MAX_READ_SIZE
    MAX_READ_SIZE = max(0, known.max_read_size)
    MAX_LIST_ENTRIES = max(1, known.max_list_entries)
    EXERCISE_DISK = known.exercise_disk
    return known.target, [argv[0], *remaining]


SELECTED_TARGET, FUZZER_ARGV = parse_args(sys.argv)
atheris.Setup(FUZZER_ARGV, test_one_input)
atheris.Fuzz()
