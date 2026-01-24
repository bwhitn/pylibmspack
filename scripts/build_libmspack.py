#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

LIBMSPACK_VERSION = os.environ.get("PYLIBMSPACK_LIBMSPACK_VERSION", "0.10.1")
LIBMSPACK_URL = (
    "https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/libmspack/"
    "0.10.1-2build2/libmspack_0.10.1.orig.tar.xz"
)
LIBMSPACK_SHA256 = "850c57442b850bf1bc0fc4ea8880903ebf2bed063c3c80782ee4626fbcb0e67d"
VENDORED_TARBALL = Path(__file__).resolve().parents[1] / "src" / "pylibmspack" / "vendor" / "libmspack_0.10.1.orig.tar.xz"

SOURCES = [
    "mspack/system.c",
    "mspack/cabd.c",
    "mspack/cabc.c",
    "mspack/chmd.c",
    "mspack/chmc.c",
    "mspack/hlpd.c",
    "mspack/hlpc.c",
    "mspack/litd.c",
    "mspack/litc.c",
    "mspack/kwajd.c",
    "mspack/kwajc.c",
    "mspack/szddd.c",
    "mspack/szddc.c",
    "mspack/oabd.c",
    "mspack/oabc.c",
    "mspack/lzxd.c",
    "mspack/lzxc.c",
    "mspack/mszipd.c",
    "mspack/mszipc.c",
    "mspack/qtmd.c",
    "mspack/lzssd.c",
    "mspack/crc32.c",
]


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, expected_sha256: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if sha256sum(dest) == expected_sha256:
            return
        dest.unlink()
    with urllib.request.urlopen(url) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)
    actual = sha256sum(dest)
    if actual != expected_sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"sha256 mismatch: {actual} != {expected_sha256}")


def extract(tar_path: Path, dst: Path) -> Path:
    if dst.exists():
        return dst
    dst.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:xz") as tf:
        try:
            tf.extractall(dst, filter="data")
        except TypeError:
            tf.extractall(dst)
    # Expect a single top-level folder
    entries = [p for p in dst.iterdir() if p.is_dir()]
    if len(entries) != 1:
        raise RuntimeError("unexpected libmspack archive layout")
    return entries[0]


def build_unix(src_root: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    cflags = os.environ.get("CFLAGS", "")
    ldflags = os.environ.get("LDFLAGS", "")
    archflags = os.environ.get("ARCHFLAGS", "")
    cppflags = os.environ.get("CPPFLAGS", "")
    import shlex
    cflag_list = []
    ldflag_list = []
    for flags in (cflags, archflags, cppflags):
        if flags:
            cflag_list += shlex.split(flags)
    for flags in (ldflags, archflags):
        if flags:
            ldflag_list += shlex.split(flags)
    include_dir = src_root / "mspack"
    sources = [str(src_root / s) for s in SOURCES]
    if sys.platform == "darwin":
        shared = out_dir / "libmspack.dylib"
        cmd = [
            cc,
            "-O2",
            "-fPIC",
            "-dynamiclib",
            "-Wl,-install_name,@rpath/libmspack.dylib",
            "-I",
            str(include_dir),
            *cflag_list,
            *sources,
            *ldflag_list,
            "-o",
            str(shared),
        ]
    else:
        shared = out_dir / "libmspack.so"
        cmd = [
            cc,
            "-O2",
            "-fPIC",
            "-shared",
            "-Wl,-soname,libmspack.so",
            "-I",
            str(include_dir),
            *cflag_list,
            *sources,
            *ldflag_list,
            "-o",
            str(shared),
        ]
    subprocess.check_call(cmd)
    return shared


def build_windows(src_root: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    include_dir = src_root / "mspack"
    sources = [str(src_root / s) for s in SOURCES]
    shared = out_dir / "mspack.dll"
    implib = out_dir / "mspack.lib"
    def_file = out_dir / "mspack.def"
    if shutil.which("cl") is None:
        raise RuntimeError(
            "Microsoft C compiler (cl.exe) not found. "
            "Install Visual Studio Build Tools and ensure the MSVC environment is set."
        )
    with def_file.open("wb") as f:
        f.write(
            b"LIBRARY mspack.dll\r\n"
            b"EXPORTS\r\n"
            b"    mspack_create_cab_decompressor\r\n"
            b"    mspack_destroy_cab_decompressor\r\n"
        )
    cmd = [
        "cl",
        "/nologo",
        "/O2",
        "/MD",
        "/LD",
        f"/I{include_dir}",
        "/DWIN32",
        "/D_WINDOWS",
        *sources,
        "/link",
        f"/DEF:{def_file}",
        f"/IMPLIB:{implib}",
        f"/OUT:{shared}",
    ]
    subprocess.check_call(cmd)
    return shared


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--src-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--tarball", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    src_dir = Path(args.src_dir).resolve()
    tarball = Path(args.tarball).resolve() if args.tarball else src_dir / "libmspack.tar.xz"

    if not tarball.exists():
        if VENDORED_TARBALL.exists():
            tarball = VENDORED_TARBALL
        elif os.environ.get("PYLIBMSPACK_ALLOW_DOWNLOAD") == "1":
            download(LIBMSPACK_URL, tarball, LIBMSPACK_SHA256)
        else:
            raise RuntimeError(
                "Vendored libmspack source tarball is missing. "
                "Expected src/pylibmspack/vendor/libmspack_0.10.1.orig.tar.xz. "
                "To allow a network download, set PYLIBMSPACK_ALLOW_DOWNLOAD=1 "
                "or pass --tarball."
            )
    elif tarball == VENDORED_TARBALL:
        actual = sha256sum(tarball)
        if actual != LIBMSPACK_SHA256:
            raise RuntimeError(f"sha256 mismatch for vendored tarball: {actual}")

    src_root = extract(tarball, src_dir)

    if sys.platform == "win32":
        shared = build_windows(src_root, out_dir)
    else:
        shared = build_unix(src_root, out_dir)

    info = {
        "version": LIBMSPACK_VERSION,
        "include_dir": str(src_root / "mspack"),
        "lib_dir": str(out_dir),
        "shared_lib": str(shared),
        "library_name": "mspack",
    }
    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(__import__("json").dumps(info), encoding="utf-8")


if __name__ == "__main__":
    main()
