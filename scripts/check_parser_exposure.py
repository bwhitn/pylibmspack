#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORMAT_TARGETS = ("cab", "chm", "szdd", "kwaj", "hlp", "oab", "oab_patch")
ALL_TARGETS = ("all", *FORMAT_TARGETS)

EXPECTED_C_METHODS = {
    "list_files",
    "list_files_bytes",
    "extract_file",
    "extract_file_bytes",
    "cab_info",
    "cab_info_bytes",
    "chm_list_files",
    "chm_list_files_bytes",
    "chm_extract_file",
    "chm_extract_file_bytes",
    "chm_info",
    "chm_info_bytes",
    "szdd_info",
    "szdd_info_bytes",
    "szdd_extract",
    "szdd_extract_bytes",
    "kwaj_info",
    "kwaj_info_bytes",
    "kwaj_extract",
    "kwaj_extract_bytes",
    "hlp_decompress",
    "hlp_decompress_bytes",
    "oab_decompress",
    "oab_decompress_bytes",
    "oab_decompress_incremental",
}

PYTHON_CLASSES = {
    "cab": ("src/pylibmspack/cab.py", "CabArchive", {"from_bytes", "files", "info", "read"}),
    "chm": ("src/pylibmspack/chm.py", "ChmArchive", {"from_bytes", "files", "info", "read"}),
    "szdd": ("src/pylibmspack/szdd.py", "SzddFile", {"from_bytes", "info", "read"}),
    "kwaj": ("src/pylibmspack/kwaj.py", "KwajFile", {"from_bytes", "info", "read"}),
    "hlp": ("src/pylibmspack/hlp.py", "HlpFile", {"from_bytes", "read"}),
    "oab": ("src/pylibmspack/oab.py", "OabFile", {"from_bytes", "read"}),
    "oab_patch": ("src/pylibmspack/oab.py", "OabPatch", {"from_bytes", "read"}),
}

SAFE_EXTRACTION_MODULES = (
    "src/pylibmspack/cab.py",
    "src/pylibmspack/chm.py",
    "src/pylibmspack/szdd.py",
    "src/pylibmspack/kwaj.py",
    "src/pylibmspack/hlp.py",
    "src/pylibmspack/oab.py",
)

SMOKE_DISK_MARKERS = {
    "cab": "CabArchive(str(cab_path))",
    "chm": "ChmArchive(str(chm_path))",
    "szdd": "SzddFile(str(szdd_path))",
    "kwaj": "KwajFile(str(kwaj_path))",
    "hlp": "HlpFile(str(hlp_path))",
    "oab": "OabFile(str(oab_path))",
    "oab_patch": "OabPatch(str(patch_path))",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def fail_if(condition: bool, failures: list[str], message: str) -> None:
    if condition:
        failures.append(message)


def literal_assignment(relative: str, name: str) -> object:
    tree = ast.parse(read(relative), filename=relative)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{relative}: missing literal assignment {name}")


def class_methods(relative: str, class_name: str) -> set[str]:
    tree = ast.parse(read(relative), filename=relative)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise ValueError(f"{relative}: missing class {class_name}")


def check_c_binding(failures: list[str]) -> None:
    text = read("src/pylibmspack/_cab.c")
    method_names = set(re.findall(r'\{"([^"]+)",\s*py_[a-z0-9_]+,\s*METH_VARARGS', text))

    missing_methods = sorted(EXPECTED_C_METHODS - method_names)
    fail_if(
        bool(missing_methods),
        failures,
        f"_cab.c is missing module methods: {', '.join(missing_methods)}",
    )

    null_creates = re.findall(r"(?:mspack_create_[a-z_]+|[a-z]+d_create)\(NULL\)", text)
    fail_if(
        bool(null_creates),
        failures,
        "_cab.c creates libmspack decompressors with NULL systems",
    )
    fail_if(
        "return calloc(1, bytes);" not in text,
        failures,
        "_cab.c mem_alloc must zero-initialize libmspack allocations with calloc",
    )

    for marker in (
        "PYLIBMSPACK_ERR_OUTPUT_LIMIT",
        "write_limit_exceeded",
        "init_memcab_system_limited",
    ):
        fail_if(marker not in text, failures, f"_cab.c missing output-limit marker {marker}")

    output_limit_checks = text.count("output_limit_err(&sys, err)")
    fail_if(
        output_limit_checks < 13,
        failures,
        f"_cab.c has only {output_limit_checks} output-limit checks; expected at least 13",
    )


def check_python_wrappers(failures: list[str]) -> None:
    for target, (relative, class_name, expected_methods) in PYTHON_CLASSES.items():
        methods = class_methods(relative, class_name)
        missing = sorted(expected_methods - methods)
        fail_if(
            bool(missing),
            failures,
            f"{target} wrapper {class_name} is missing methods: {', '.join(missing)}",
        )

    for relative in SAFE_EXTRACTION_MODULES:
        text = read(relative)
        fail_if(
            "ensure_safe_output_path" not in text,
            failures,
            f"{relative} is missing safe-output path checks",
        )
        fail_if(
            "_ERR_OUTPUT_LIMIT" not in text or "max_size" not in text,
            failures,
            f"{relative} is missing Python output-limit handling",
        )

    for relative in ("src/pylibmspack/cab.py", "src/pylibmspack/chm.py"):
        text = read(relative)
        fail_if(
            "max_total_size" not in text or "max_files" not in text,
            failures,
            f"{relative} bulk extraction is missing max_total_size/max_files",
        )


def check_fuzz_exposure(failures: list[str]) -> None:
    corpus_targets = tuple(literal_assignment("fuzz/corpus.py", "TARGETS"))
    fail_if(
        corpus_targets != ALL_TARGETS,
        failures,
        f"fuzz/corpus.py TARGETS is {corpus_targets!r}, expected {ALL_TARGETS!r}",
    )

    selectors = dict(literal_assignment("fuzz/corpus.py", "TARGET_SELECTORS"))
    fail_if(
        tuple(selectors) != FORMAT_TARGETS,
        failures,
        "fuzz/corpus.py TARGET_SELECTORS does not cover every format target in order",
    )
    fail_if(
        tuple(selectors.values()) != tuple(range(len(FORMAT_TARGETS))),
        failures,
        "fuzz/corpus.py TARGET_SELECTORS values must be contiguous from zero",
    )

    atheris_targets = tuple(literal_assignment("fuzz/atheris_fuzzer.py", "TARGETS"))
    fail_if(
        atheris_targets != ALL_TARGETS,
        failures,
        f"fuzz/atheris_fuzzer.py TARGETS is {atheris_targets!r}, expected {ALL_TARGETS!r}",
    )
    atheris_text = read("fuzz/atheris_fuzzer.py")
    for target in FORMAT_TARGETS:
        fail_if(f"def fuzz_{target}(" not in atheris_text, failures, f"missing fuzz_{target}()")
    for marker in ("EXERCISE_DISK", "_with_disk", "--exercise-disk"):
        fail_if(marker not in atheris_text, failures, f"Atheris harness missing {marker}")

    native_text = read("fuzz/libmspack_fuzzer.c")
    fail_if(
        "return calloc(1, bytes);" not in native_text,
        failures,
        "native fuzzer allocator is not zeroed",
    )
    fail_if("MAX_OUTPUT_SIZE" not in native_text, failures, "native fuzzer lacks output cap")
    for target in FORMAT_TARGETS:
        macro = target.upper()
        fail_if(
            f"#define FUZZ_TARGET_{macro}" not in native_text,
            failures,
            f"native fuzzer missing FUZZ_TARGET_{macro}",
        )
        fail_if(
            f"static void target_{target}(" not in native_text,
            failures,
            f"native fuzzer missing target_{target}()",
        )

    smoke_text = read("scripts/fuzz_smoke.py")
    for target, marker in SMOKE_DISK_MARKERS.items():
        fail_if(
            marker not in smoke_text, failures, f"fuzz_smoke.py missing disk smoke for {target}"
        )

    runner_text = read("scripts/run_atheris.py")
    fail_if(
        "--exercise-disk" not in runner_text, failures, "run_atheris.py missing --exercise-disk"
    )

    docker_text = read("fuzz/Dockerfile")
    fail_if(
        "scripts/run_atheris.py --exercise-disk" not in docker_text,
        failures,
        "fuzz/Dockerfile Atheris smoke does not exercise disk-backed parser APIs",
    )


def check_ci(failures: list[str]) -> None:
    ci_text = read(".github/workflows/ci.yml")
    fail_if(
        "python scripts/check_parser_exposure.py" not in ci_text,
        failures,
        "CI lint job does not run scripts/check_parser_exposure.py",
    )

    security_text = read(".github/workflows/security.yml")
    fail_if(
        "--exercise-disk" not in security_text,
        failures,
        "security Atheris job does not exercise disk-backed parser APIs",
    )


def main() -> int:
    failures: list[str] = []
    check_c_binding(failures)
    check_python_wrappers(failures)
    check_fuzz_exposure(failures)
    check_ci(failures)

    if failures:
        for failure in failures:
            print(f"parser exposure check failed: {failure}", file=sys.stderr)
        return 1
    print("parser exposure checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
