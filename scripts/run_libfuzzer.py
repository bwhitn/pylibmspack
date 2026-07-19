#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fuzz.corpus import TARGETS, dictionary_for, seed_corpus  # noqa: E402


def target_name(binary: Path) -> str:
    prefix = "pylibmspack_fuzz_"
    name = binary.name
    if name.startswith(prefix):
        return name[len(prefix) :]
    return name


def parse_extra_args(extra_args: list[str]) -> list[str]:
    if extra_args and extra_args[0] == "--":
        return extra_args[1:]
    return extra_args


def corpus_workspace(
    corpus_root: str | None,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if corpus_root:
        root = (ROOT / corpus_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root, None
    tmp = tempfile.TemporaryDirectory(prefix="pylibmspack-libfuzzer-corpus-")
    return Path(tmp.name), tmp


def selected_binaries(fuzzers_dir: Path, targets: list[str] | None) -> list[Path]:
    target_set = set(targets or TARGETS)
    binaries = sorted(
        path
        for path in fuzzers_dir.glob("pylibmspack_fuzz_*")
        if path.is_file() and os.access(path, os.X_OK) and target_name(path) in target_set
    )
    if not binaries:
        selected = ", ".join(sorted(target_set))
        raise RuntimeError(f"no selected libFuzzer binaries found in {fuzzers_dir}: {selected}")
    return binaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fuzzers-dir", default="build/libfuzzer")
    parser.add_argument("--corpus-root", default="")
    parser.add_argument("--artifact-dir", default="build/fuzz-artifacts/libfuzzer")
    parser.add_argument("--dict-dir", default=str(ROOT / "fuzz" / "dictionaries"))
    parser.add_argument("--target", choices=TARGETS, action="append")
    parser.add_argument("--runs", type=int, default=256)
    parser.add_argument("--max-total-time", type=int, default=0)
    parser.add_argument("--max-len", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--rss-limit-mb", type=int, default=1024)
    parser.add_argument("--jobs", type=int, default=0)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--value-profile", action="store_true")
    parser.add_argument("--no-dict", action="store_true")
    parser.add_argument("--include-fixtures", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--print-cmd", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    fuzzers_dir = (ROOT / args.fuzzers_dir).resolve()
    binaries = selected_binaries(fuzzers_dir, args.target)
    artifact_root = (ROOT / args.artifact_dir).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    dict_dir = (ROOT / args.dict_dir).resolve()
    extra_args = parse_extra_args(args.extra_args)
    env = os.environ.copy()
    env.setdefault("ASAN_OPTIONS", "abort_on_error=1:detect_leaks=0:strict_string_checks=1")
    env.setdefault("UBSAN_OPTIONS", "halt_on_error=1:print_stacktrace=1")

    corpus_root, tmp = corpus_workspace(args.corpus_root or None)
    try:
        for binary in binaries:
            target = target_name(binary)
            corpus_dir = corpus_root / target
            artifact_dir = artifact_root / target
            seed_corpus(corpus_dir, target, include_fixtures=args.include_fixtures)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                str(binary),
                str(corpus_dir),
                f"-max_len={args.max_len}",
                f"-timeout={args.timeout}",
                f"-rss_limit_mb={args.rss_limit_mb}",
                f"-artifact_prefix={artifact_dir}/",
                "-print_final_stats=1",
            ]
            if args.runs > 0:
                cmd.append(f"-runs={args.runs}")
            if args.max_total_time > 0:
                cmd.append(f"-max_total_time={args.max_total_time}")
            if args.jobs > 0:
                cmd.append(f"-jobs={args.jobs}")
            if args.workers > 0:
                cmd.append(f"-workers={args.workers}")
            if args.value_profile:
                cmd.append("-use_value_profile=1")
            if not args.no_dict:
                dict_file = dictionary_for(target, dict_dir)
                if dict_file:
                    cmd.append(f"-dict={dict_file}")
            cmd.extend(extra_args)
            if args.print_cmd:
                print(" ".join(cmd))
            subprocess.check_call(cmd, cwd=ROOT, env=env)
    finally:
        if tmp is not None:
            tmp.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
