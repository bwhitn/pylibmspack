#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sysconfig
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "src" / "pylibmspack" / "_cab.c"
VENDORED = ROOT / "src" / "pylibmspack" / "vendor" / "libmspack_0.11.orig.tar.gz"


def extract_include_dir(tmp_dir: Path) -> Path:
    src_dir = tmp_dir / "libmspack-src"
    src_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(VENDORED, "r:*") as tf:
        try:
            tf.extractall(src_dir, filter="data")
        except TypeError:
            tf.extractall(src_dir)
    entries = [path for path in src_dir.iterdir() if path.is_dir()]
    if len(entries) != 1:
        raise RuntimeError("unexpected libmspack archive layout")
    include_dir = entries[0] / "mspack"
    if not (include_dir / "mspack.h").exists():
        raise RuntimeError(f"missing mspack.h in {include_dir}")
    return include_dir


def compiler() -> str:
    configured = os.environ.get("CC")
    if configured:
        return configured
    for candidate in ("cc", "clang", "gcc"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("no C compiler found")


def python_include_args() -> list[str]:
    include_dirs = {
        path for path in (sysconfig.get_path("include"), sysconfig.get_path("platinclude")) if path
    }
    return [flag for path in sorted(include_dirs) for flag in ("-isystem", path)]


def main() -> int:
    if not VENDORED.exists():
        raise RuntimeError(f"missing vendored libmspack tarball: {VENDORED}")

    with tempfile.TemporaryDirectory(prefix="pylibmspack-c-check-") as tmp:
        include_dir = extract_include_dir(Path(tmp))
        cmd = [
            compiler(),
            "-fsyntax-only",
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-I",
            str(include_dir),
            *python_include_args(),
            str(BINDING),
        ]
        subprocess.check_call(cmd, cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
