#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from check_c_binding import BINDING, ROOT, extract_include_dir, python_include_args


def tool_path(name: str, *, require: bool) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for prefix in ("/usr/local/opt/llvm", "/opt/homebrew/opt/llvm"):
        candidate = Path(prefix) / "bin" / name
        if candidate.exists():
            return str(candidate)
    if require:
        raise RuntimeError(f"{name} is required but was not found")
    print(f"skipping {name}: not installed", file=sys.stderr)
    return None


def include_flags(include_dir: Path) -> list[str]:
    flags = ["-I", str(include_dir)]
    for flag in python_include_args():
        flags.append("-I" if flag == "-isystem" else flag)
    return flags


def run_cppcheck(cppcheck: str, include_dir: Path) -> None:
    cmd = [
        cppcheck,
        "--enable=warning,performance,portability",
        "--error-exitcode=1",
        "--std=c99",
        "--quiet",
        "--suppress=missingIncludeSystem",
        "-D__GNUC__=13",
        "-D__GNUC_MINOR__=0",
        "-D__has_builtin(x)=0",
        "-D__has_feature(x)=0",
        *include_flags(include_dir),
        str(BINDING),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def run_clang_tidy(clang_tidy: str, include_dir: Path) -> None:
    checks = ",".join(
        [
            "-*",
            "clang-analyzer-core.*",
            "clang-analyzer-security.*",
            "clang-analyzer-unix.*",
            "clang-analyzer-deadcode.*",
            "bugprone-sizeof-expression",
            "bugprone-suspicious-missing-comma",
        ]
    )
    cmd = [
        clang_tidy,
        str(BINDING),
        f"--checks={checks}",
        "--warnings-as-errors=*",
        "--quiet",
        "--",
        "-std=c99",
        "-Wno-unused-parameter",
        "-I",
        str(include_dir),
        *python_include_args(),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="store_true", help="fail when a tool is missing")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pylibmspack-native-static-") as tmp:
        include_dir = extract_include_dir(Path(tmp))
        cppcheck = tool_path("cppcheck", require=args.require)
        clang_tidy = tool_path("clang-tidy", require=args.require)
        if cppcheck:
            run_cppcheck(cppcheck, include_dir)
        if clang_tidy:
            run_clang_tidy(clang_tidy, include_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
