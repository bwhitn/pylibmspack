#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fuzz.corpus import TARGETS, dictionary_for, seed_inputs  # noqa: E402

TARGET_RSS_LIMIT_MB_OVERRIDES = {
    "chm": 2048,
}


def fuzzer_name(target: str) -> str:
    return f"pylibmspack_fuzz_{target}"


def rss_limit_mb_for(target: str, default: int) -> int:
    return max(default, TARGET_RSS_LIMIT_MB_OVERRIDES.get(target, default))


def write_options(
    out_dir: Path, target: str, max_len: int, timeout: int, rss_limit_mb: int
) -> None:
    name = fuzzer_name(target)
    options = [
        "[libfuzzer]",
        f"max_len = {max_len}",
        f"timeout = {timeout}",
        f"rss_limit_mb = {rss_limit_mb}",
    ]
    if dictionary_for(target):
        options.append(f"dict = {name}.dict")
    (out_dir / f"{name}.options").write_text("\n".join(options) + "\n")


def copy_dictionary(out_dir: Path, target: str) -> None:
    dictionary = dictionary_for(target)
    if dictionary is None:
        return
    shutil.copy2(dictionary, out_dir / f"{fuzzer_name(target)}.dict")


def write_seed_corpus(out_dir: Path, target: str, include_fixtures: bool) -> None:
    seed_zip = out_dir / f"{fuzzer_name(target)}_seed_corpus.zip"
    with zipfile.ZipFile(seed_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in seed_inputs(target, include_fixtures=include_fixtures).items():
            zf.writestr(name, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="build/libfuzzer")
    parser.add_argument("--target", choices=TARGETS, action="append")
    parser.add_argument("--max-len", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--rss-limit-mb", type=int, default=1024)
    parser.add_argument("--include-fixtures", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = args.target or list(TARGETS)
    for target in selected:
        copy_dictionary(out_dir, target)
        write_options(
            out_dir,
            target,
            args.max_len,
            args.timeout,
            rss_limit_mb_for(target, args.rss_limit_mb),
        )
        write_seed_corpus(out_dir, target, include_fixtures=args.include_fixtures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
