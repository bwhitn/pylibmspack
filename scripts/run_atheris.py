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

HARNESS = ROOT / "fuzz" / "atheris_fuzzer.py"


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
    tmp = tempfile.TemporaryDirectory(prefix="pylibmspack-atheris-corpus-")
    return Path(tmp.name), tmp


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--corpus-root", default="")
    parser.add_argument("--artifact-dir", default="build/fuzz-artifacts/atheris")
    parser.add_argument("--dict-dir", default=str(ROOT / "fuzz" / "dictionaries"))
    parser.add_argument("--target", choices=TARGETS, action="append")
    parser.add_argument("--runs", type=int, default=256)
    parser.add_argument("--max-len", type=int, default=4096)
    parser.add_argument("--max-read-size", type=int, default=4096)
    parser.add_argument("--max-list-entries", type=int, default=4)
    parser.add_argument("--exercise-disk", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--jobs", type=int, default=0)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-dict", action="store_true")
    parser.add_argument("--include-fixtures", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--print-cmd", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    selected = args.target or list(TARGETS)
    artifact_root = (ROOT / args.artifact_dir).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    dict_dir = (ROOT / args.dict_dir).resolve()
    extra_args = parse_extra_args(args.extra_args)

    env = os.environ.copy()
    env.setdefault("PYTHONHASHSEED", "0")

    corpus_root, tmp = corpus_workspace(args.corpus_root or None)
    try:
        for target in selected:
            corpus_dir = corpus_root / target
            artifact_dir = artifact_root / target
            seed_corpus(corpus_dir, target, include_fixtures=args.include_fixtures)
            artifact_dir.mkdir(parents=True, exist_ok=True)

            cmd = [
                args.python,
                str(HARNESS),
                "--target",
                target,
                "--max-read-size",
                str(args.max_read_size),
                "--max-list-entries",
                str(args.max_list_entries),
            ]
            if args.exercise_disk:
                cmd.append("--exercise-disk")
            cmd.extend(
                [
                    str(corpus_dir),
                    f"-max_len={args.max_len}",
                    f"-timeout={args.timeout}",
                    f"-artifact_prefix={artifact_dir}/",
                ]
            )
            if args.runs > 0:
                cmd.append(f"-atheris_runs={args.runs}")
            if args.jobs > 0:
                cmd.append(f"-jobs={args.jobs}")
            if args.workers > 0:
                cmd.append(f"-workers={args.workers}")
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
