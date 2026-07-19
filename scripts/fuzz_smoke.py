#!/usr/bin/env python3
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path
from typing import Callable

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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fuzz.corpus import seed_inputs  # noqa: E402

EXPECTED_EXCEPTIONS = (MspackError, OSError, ValueError)


def corpus() -> list[bytes]:
    rng = random.Random(0x4D535041)
    cases = list(seed_inputs("all").values())
    for size in (1, 2, 3, 4, 8, 16, 32, 64):
        cases.append(bytes(rng.randrange(0, 256) for _ in range(size)))
    return cases


def expect_handled(fn: Callable[[], object]) -> None:
    try:
        fn()
    except EXPECTED_EXCEPTIONS:
        return


def write_input(tmp: Path, name: str, data: bytes) -> Path:
    path = tmp / name
    path.write_bytes(data)
    return path


def exercise_payload(data: bytes, tmp: Path) -> None:
    expect_handled(lambda: CabArchive.from_bytes(data).info())
    expect_handled(lambda: CabArchive.from_bytes(data).files())
    expect_handled(lambda: CabArchive.from_bytes(data).read("member.txt", max_size=4096))
    cab_path = write_input(tmp, "sample.cab", data)
    expect_handled(lambda: CabArchive(str(cab_path)).info())
    expect_handled(lambda: CabArchive(str(cab_path)).files())
    expect_handled(lambda: CabArchive(str(cab_path)).read("member.txt", max_size=4096))

    expect_handled(lambda: ChmArchive.from_bytes(data).info())
    expect_handled(lambda: ChmArchive.from_bytes(data).files())
    expect_handled(lambda: ChmArchive.from_bytes(data).read("index.html", max_size=4096))
    chm_path = write_input(tmp, "sample.chm", data)
    expect_handled(lambda: ChmArchive(str(chm_path)).info())
    expect_handled(lambda: ChmArchive(str(chm_path)).files())
    expect_handled(lambda: ChmArchive(str(chm_path)).read("index.html", max_size=4096))

    expect_handled(lambda: SzddFile.from_bytes(data, name="sample.tx_").info())
    expect_handled(lambda: SzddFile.from_bytes(data, name="sample.tx_").read(max_size=4096))
    szdd_path = write_input(tmp, "sample.tx_", data)
    expect_handled(lambda: SzddFile(str(szdd_path)).info())
    expect_handled(lambda: SzddFile(str(szdd_path)).read(max_size=4096))

    expect_handled(lambda: KwajFile.from_bytes(data, name="sample.kwj").info())
    expect_handled(lambda: KwajFile.from_bytes(data, name="sample.kwj").read(max_size=4096))
    kwaj_path = write_input(tmp, "sample.kwj", data)
    expect_handled(lambda: KwajFile(str(kwaj_path)).info())
    expect_handled(lambda: KwajFile(str(kwaj_path)).read(max_size=4096))

    expect_handled(lambda: HlpFile.from_bytes(data, name="sample.hlp").read(max_size=4096))
    expect_handled(
        lambda: HlpFile.from_bytes(data, name="sample.hlp").extract(
            str(tmp),
            out_name="hlp.bin",
            max_size=4096,
        )
    )
    hlp_path = write_input(tmp, "sample.hlp", data)
    expect_handled(lambda: HlpFile(str(hlp_path)).read(max_size=4096))
    expect_handled(
        lambda: HlpFile(str(hlp_path)).extract(
            str(tmp),
            out_name="hlp-disk.bin",
            max_size=4096,
        )
    )

    expect_handled(
        lambda: OabFile.from_bytes(data, name="sample.lzx").read(max_size=4096, decompbuf=128)
    )
    expect_handled(
        lambda: OabFile.from_bytes(data, name="sample.lzx").extract(
            str(tmp),
            out_name="oab.bin",
            decompbuf=128,
            max_size=4096,
        )
    )
    oab_path = write_input(tmp, "sample.lzx", data)
    expect_handled(lambda: OabFile(str(oab_path)).read(max_size=4096, decompbuf=128))
    expect_handled(
        lambda: OabFile(str(oab_path)).extract(
            str(tmp),
            out_name="oab-disk.bin",
            decompbuf=128,
            max_size=4096,
        )
    )
    expect_handled(
        lambda: OabPatch.from_bytes(data, name="patch.lzx").read(
            b"base",
            max_size=4096,
            decompbuf=128,
        )
    )
    patch_path = write_input(tmp, "patch.lzx", data)
    base_path = write_input(tmp, "base.oab", b"base")
    expect_handled(
        lambda: OabPatch(str(patch_path)).read(
            str(base_path),
            max_size=4096,
            decompbuf=128,
        )
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pylibmspack-fuzz-smoke-") as tmp:
        tmp_path = Path(tmp)
        for data in corpus():
            exercise_payload(data, tmp_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
