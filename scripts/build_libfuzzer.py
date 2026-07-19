#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from build_libmspack import SOURCES, VENDORED_TARBALL, extract

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "fuzz" / "libmspack_fuzzer.c"

TARGETS = {
    "all": "FUZZ_TARGET_ALL",
    "cab": "FUZZ_TARGET_CAB",
    "chm": "FUZZ_TARGET_CHM",
    "szdd": "FUZZ_TARGET_SZDD",
    "kwaj": "FUZZ_TARGET_KWAJ",
    "hlp": "FUZZ_TARGET_HLP",
    "oab": "FUZZ_TARGET_OAB",
    "oab_patch": "FUZZ_TARGET_OAB_PATCH",
}


def find_clang(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    if os.environ.get("CC"):
        return os.environ["CC"]
    for candidate in (
        "/usr/local/opt/llvm/bin/clang",
        "/opt/homebrew/opt/llvm/bin/clang",
        "clang",
    ):
        found = shutil.which(candidate) if "/" not in candidate else candidate
        if found and Path(found).exists():
            return found
    raise RuntimeError("clang is required to build libFuzzer targets")


def find_cxx(explicit: str | None = None, fallback: str | None = None) -> str:
    if explicit:
        return explicit
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if fallback:
        return fallback
    for candidate in (
        "/usr/local/opt/llvm/bin/clang++",
        "/opt/homebrew/opt/llvm/bin/clang++",
        "clang++",
    ):
        found = shutil.which(candidate) if "/" not in candidate else candidate
        if found and Path(found).exists():
            return found
    raise RuntimeError("clang++ is required to link libFuzzer targets")


def split_flags(value: str) -> list[str]:
    return shlex.split(value) if value else []


def env_compile_flags() -> list[str]:
    flags: list[str] = []
    for name in ("CFLAGS", "CPPFLAGS"):
        flags.extend(split_flags(os.environ.get(name, "")))
    return flags


def env_link_flags() -> list[str]:
    flags: list[str] = []
    for name in ("CXXFLAGS", "LDFLAGS"):
        flags.extend(split_flags(os.environ.get(name, "")))
    return flags


def base_compile_flags() -> list[str]:
    return ["-std=c99", "-g", "-O1", "-fno-omit-frame-pointer"]


def fuzzer_name(target_name: str) -> str:
    return f"pylibmspack_fuzz_{target_name}"


def build_target(
    cc: str,
    cxx: str,
    include_dir: Path,
    objects: list[Path],
    out_dir: Path,
    target_name: str,
    target_macro: str,
    compile_flags: list[str],
    link_flags: list[str],
    engine_flags: list[str],
) -> Path:
    harness_obj = out_dir / "obj" / f"fuzz_{target_name}.o"
    output = out_dir / fuzzer_name(target_name)
    compile_cmd = [
        cc,
        *compile_flags,
        "-I",
        str(include_dir),
        f"-DFUZZ_TARGET={target_macro}",
        "-c",
        str(HARNESS),
        "-o",
        str(harness_obj),
    ]
    subprocess.check_call(compile_cmd, cwd=ROOT)

    cmd = [
        cxx,
        *link_flags,
        str(harness_obj),
        *(str(obj) for obj in objects),
        *engine_flags,
        "-o",
        str(output),
    ]
    subprocess.check_call(cmd, cwd=ROOT)
    return output


def compile_objects(
    cc: str,
    src_root: Path,
    obj_dir: Path,
    compile_flags: list[str],
) -> list[Path]:
    include_dir = src_root / "mspack"
    obj_dir.mkdir(parents=True, exist_ok=True)
    objects: list[Path] = []
    for source in SOURCES:
        src = src_root / source
        obj = obj_dir / (source.replace("/", "_") + ".o")
        cmd = [
            cc,
            *compile_flags,
            "-I",
            str(include_dir),
            "-c",
            str(src),
            "-o",
            str(obj),
        ]
        subprocess.check_call(cmd, cwd=ROOT)
        objects.append(obj)
    return objects


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="build/libfuzzer")
    parser.add_argument("--cc", default="")
    parser.add_argument("--cxx", default="")
    parser.add_argument(
        "--engine-lib",
        default=os.environ.get("LIB_FUZZING_ENGINE", ""),
        help="fuzzing engine link flags, normally $LIB_FUZZING_ENGINE under OSS-Fuzz",
    )
    parser.add_argument(
        "--use-env-flags",
        action="store_true",
        help="honor CFLAGS/CPPFLAGS/CXXFLAGS/LDFLAGS from the environment",
    )
    parser.add_argument(
        "--sanitizers",
        default="address",
        help="comma-separated sanitizer list for local -fsanitize=fuzzer builds",
    )
    parser.add_argument("--target", choices=sorted(TARGETS), action="append")
    args = parser.parse_args()

    selected = args.target or sorted(TARGETS)
    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cc = find_clang(args.cc or None)
    cxx = find_cxx(args.cxx or None, fallback=cc)
    engine_flags = split_flags(args.engine_lib)
    compile_flags = base_compile_flags()
    link_flags: list[str] = []

    if args.use_env_flags or engine_flags:
        compile_flags.extend(env_compile_flags())
        link_flags.extend(env_link_flags())

    if engine_flags:
        # OSS-Fuzz/ClusterFuzzLite provide sanitizer and coverage instrumentation
        # in CFLAGS/CXXFLAGS and the fuzzing engine in LIB_FUZZING_ENGINE.
        pass
    else:
        compile_flags.append(f"-fsanitize=fuzzer-no-link,{args.sanitizers}")
        link_flags.append(f"-fsanitize=fuzzer,{args.sanitizers}")

    with tempfile.TemporaryDirectory(prefix="pylibmspack-libfuzzer-src-") as tmp:
        src_root = extract(VENDORED_TARBALL, Path(tmp) / "src")
        include_dir = src_root / "mspack"
        objects = compile_objects(
            cc,
            src_root,
            out_dir / "obj",
            compile_flags,
        )
        for target_name in selected:
            output = build_target(
                cc,
                cxx,
                include_dir,
                objects,
                out_dir,
                target_name,
                TARGETS[target_name],
                compile_flags,
                link_flags,
                engine_flags,
            )
            print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
