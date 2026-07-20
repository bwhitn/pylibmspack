#!/bin/bash -eu

cd "$SRC/pylibmspack"

target_spec="${CFL_TARGETS:-${CFL_EXTRA_TARGETS:-}}"
target_file=".clusterfuzzlite/targets"
if [[ -z "$target_spec" && -f "$target_file" ]]; then
  target_spec="$(tr '\n' ',' < "$target_file")"
fi

target_args=()
if [[ -n "$target_spec" ]]; then
  IFS=',' read -r -a targets <<< "$target_spec"
  for target in "${targets[@]}"; do
    target="${target//[[:space:]]/}"
    if [[ -n "$target" ]]; then
      target_args+=(--target "$target")
    fi
  done
fi

python3 scripts/build_libfuzzer.py \
  --out-dir "$OUT" \
  --cc "$CC" \
  --cxx "$CXX" \
  --engine-lib="$LIB_FUZZING_ENGINE" \
  --use-env-flags \
  "${target_args[@]}"

python3 scripts/export_fuzz_artifacts.py \
  --out-dir "$OUT" \
  --max-len 2097152 \
  --timeout 10 \
  --rss-limit-mb 1024 \
  "${target_args[@]}"
