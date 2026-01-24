#!/usr/bin/env python3
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
VENDORED = ROOT / "src" / "pylibmspack" / "vendor" / "libmspack_0.10.1.orig.tar.xz"


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    if not VENDORED.exists():
        raise SystemExit(f"Missing vendored tarball: {VENDORED}")

    with tarfile.open(VENDORED, "r:xz") as tf:
        mszip = tf.getmember("libmspack-0.10.1alpha/test/test_files/cabd/mszip_lzx_qtm.cab")
        normal = tf.getmember("libmspack-0.10.1alpha/test/test_files/cabd/normal_2files_1folder.cab")
        (FIXTURES_DIR / "small_mszip.cab").write_bytes(tf.extractfile(mszip).read())
        normal_bytes = tf.extractfile(normal).read()
        (FIXTURES_DIR / "normal_2files_1folder.cab").write_bytes(normal_bytes)

    # Build traversal.cab by rewriting a filename in normal_2files_1folder.cab
    needle = b"hello.c\\x00"
    idx = normal_bytes.find(needle)
    if idx == -1:
        raise SystemExit("needle not found in normal_2files_1folder.cab")
    replacement = b"..\\\\..\\\\a\\x00"
    if len(replacement) != len(needle):
        raise SystemExit("replacement length mismatch")
    traversal = normal_bytes[:idx] + replacement + normal_bytes[idx + len(needle):]
    (FIXTURES_DIR / "traversal.cab").write_bytes(traversal)
    print("wrote fixtures to", FIXTURES_DIR)


if __name__ == "__main__":
    main()
