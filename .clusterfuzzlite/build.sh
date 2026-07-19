#!/bin/bash -eu

cd "$SRC/pylibmspack"

python3 scripts/build_libfuzzer.py \
  --out-dir "$OUT" \
  --cc "$CC" \
  --cxx "$CXX" \
  --engine-lib="$LIB_FUZZING_ENGINE" \
  --use-env-flags

python3 scripts/export_fuzz_artifacts.py \
  --out-dir "$OUT" \
  --max-len 2097152 \
  --timeout 10 \
  --rss-limit-mb 1024
