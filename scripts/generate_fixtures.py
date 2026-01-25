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
        kwaj = tf.getmember("libmspack-0.10.1alpha/test/test_files/kwajd/f00.kwj")
        (FIXTURES_DIR / "small_mszip.cab").write_bytes(tf.extractfile(mszip).read())
        normal_bytes = tf.extractfile(normal).read()
        (FIXTURES_DIR / "normal_2files_1folder.cab").write_bytes(normal_bytes)
        (FIXTURES_DIR / "sample.kwj").write_bytes(tf.extractfile(kwaj).read())

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

    # Generate a minimal SZDD fixture using literal-only encoding.
    payload = b"SZDDTEST"
    expected_dir = FIXTURES_DIR / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    (expected_dir / "szdd.txt").write_bytes(payload)

    sig = bytes([0x53, 0x5A, 0x44, 0x44, 0x88, 0xF0, 0x27, 0x33])
    mode = bytes([0x41])
    missing = bytes([ord("t")])
    length = len(payload).to_bytes(4, "little")
    control = bytes([0xFF])
    compressed = control + payload
    out = sig + mode + missing + length + compressed
    (FIXTURES_DIR / "sample.tx_").write_bytes(out)
    print("wrote fixtures to", FIXTURES_DIR)


if __name__ == "__main__":
    main()
