from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DICTIONARIES = ROOT / "fuzz" / "dictionaries"

TARGETS = ("all", "cab", "chm", "szdd", "kwaj", "hlp", "oab", "oab_patch")
TARGET_SELECTORS = {
    "cab": 0,
    "chm": 1,
    "szdd": 2,
    "kwaj": 3,
    "hlp": 4,
    "oab": 5,
    "oab_patch": 6,
}
TARGET_EXTENSIONS = {
    "cab": (".cab",),
    "chm": (".chm",),
    "szdd": (".tx_", ".sz_"),
    "kwaj": (".kwj",),
}


def le32(value: int) -> bytes:
    return value.to_bytes(4, "little")


def mshelp_literals(payload: bytes) -> bytes:
    chunks: list[bytes] = []
    for idx in range(0, len(payload), 8):
        chunks.append(b"\x00" + payload[idx : idx + 8])
    return b"".join(chunks)


def full_oab(payload: bytes) -> bytes:
    block_max = max(len(payload), 1)
    header = le32(3) + le32(1) + le32(block_max) + le32(len(payload))
    block = le32(0) + le32(len(payload)) + le32(len(payload)) + le32(0)
    return header + block + payload


def oab_patch_pair(
    patch_payload: bytes = b"patched payload", base_payload: bytes = b"base"
) -> bytes:
    patch = full_oab(patch_payload)
    base = base_payload[: len(patch)].ljust(len(patch), b"\x00")
    return patch + base


def truncated(data: bytes, limit: int = 32) -> dict[str, bytes]:
    return {f"trunc_{idx:02d}": data[:idx] for idx in range(min(len(data), limit))}


def mutated(data: bytes, limit: int = 128) -> dict[str, bytes]:
    cases: dict[str, bytes] = {}
    if not data:
        return cases
    for idx in range(0, min(len(data), limit), 7):
        buf = bytearray(data[: min(len(data), limit)])
        buf[idx] ^= 0xFF
        cases[f"flip_{idx:03d}"] = bytes(buf)
    return cases


def generic_seed_inputs() -> dict[str, bytes]:
    return {
        "empty": b"",
        "nul": b"\x00",
        "ff": b"\xff",
        "ascii": b"not an archive",
        "zeros_32": b"\x00" * 32,
        "ones_32": b"\xff" * 32,
    }


def format_seed_inputs(target: str) -> dict[str, bytes]:
    if target == "cab":
        cab_stub = b"MSCF" + (b"\x00" * 32)
        seeds = {
            "cab_magic": b"MSCF",
            "cab_stub": cab_stub,
            "cab_reserved_signature": b"MSCF\x00\x00\x00\x00\x2c\x00\x00\x00",
        }
        seeds.update({f"cab_{name}": data for name, data in truncated(cab_stub).items()})
        return seeds
    if target == "chm":
        chm_stub = b"ITSF\x03\x00\x00\x00" + (b"\x00" * 56)
        seeds = {
            "chm_magic": b"ITSF",
            "chm_stub": chm_stub,
            "chm_section_magic": b"ITSP\x01\x00\x00\x00",
            "chm_name_index": b"/#SYSTEM\x00/#STRINGS\x00/#URLTBL\x00/#URLSTR\x00",
        }
        seeds.update({f"chm_{name}": data for name, data in truncated(chm_stub).items()})
        return seeds
    if target == "szdd":
        szdd_stub = b"SZDD\x88\xf0\x27\x33A" + (b"\x00" * 32)
        seeds = {
            "szdd_magic": b"SZDD",
            "szdd_stub": szdd_stub,
            "szdd_qbasic_header": b"SZDD\x88\xf0\x27\x33A\x00",
        }
        seeds.update({f"szdd_{name}": data for name, data in truncated(szdd_stub).items()})
        return seeds
    if target == "kwaj":
        kwaj_stub = b"KWAJ\x88\xf0\x27\xd1" + (b"\x00" * 32)
        seeds = {
            "kwaj_magic": b"KWAJ",
            "kwaj_short": b"\x03",
            "kwaj_stub": kwaj_stub,
            "kwaj_header_flags": b"KWAJ\x88\xf0\x27\xd1\x00\x00",
        }
        seeds.update({f"kwaj_{name}": data for name, data in truncated(kwaj_stub).items()})
        return seeds
    if target == "hlp":
        literal_stream = mshelp_literals(b"MS Help LZSS payload\n")
        seeds = {
            "hlp_winhelp_container_magic": b"?_\x03\x00not-a-raw-stream",
            "hlp_literal_stream": literal_stream,
            "hlp_empty_control": b"\x00",
            "hlp_backrefs": b"\xff\x00\x00\x00\x00",
        }
        seeds.update({f"hlp_{name}": data for name, data in truncated(literal_stream).items()})
        return seeds
    if target == "oab":
        oab = full_oab(b"OAB payload")
        seeds = {
            "oab_full": oab,
            "oab_empty_payload": full_oab(b""),
            "oab_large_literal": full_oab(b"A" * 64),
        }
        seeds.update({f"oab_{name}": data for name, data in truncated(oab).items()})
        return seeds
    if target == "oab_patch":
        patch = oab_patch_pair()
        seeds = {
            "oab_patch_pair": patch,
            "oab_patch_empty": oab_patch_pair(b"", b"base"),
        }
        seeds.update({f"oab_patch_{name}": data for name, data in truncated(patch).items()})
        return seeds
    raise ValueError(f"unknown fuzz target: {target}")


def fixture_seed_inputs(target: str, fixtures_dir: Path = FIXTURES) -> dict[str, bytes]:
    extensions = TARGET_EXTENSIONS.get(target, ())
    if not fixtures_dir.exists():
        return {}

    seeds: dict[str, bytes] = {}
    for fixture in sorted(fixtures_dir.glob("*")):
        if not fixture.is_file() or fixture.suffix.lower() not in extensions:
            continue
        data = fixture.read_bytes()
        stem = fixture.name.replace("/", "_")
        seeds[f"fixture_{stem}"] = data
        seeds.update({f"fixture_{stem}_{name}": value for name, value in truncated(data).items()})
        seeds.update({f"fixture_{stem}_{name}": value for name, value in mutated(data).items()})
    return seeds


def seed_inputs(target: str, include_fixtures: bool = True) -> dict[str, bytes]:
    if target not in TARGETS:
        raise ValueError(f"unknown fuzz target: {target}")

    if target == "all":
        seeds = generic_seed_inputs()
        for child_target, selector in TARGET_SELECTORS.items():
            for name, data in seed_inputs(child_target, include_fixtures).items():
                seeds[f"{child_target}_{name}"] = bytes([selector]) + data
        return seeds

    seeds = generic_seed_inputs()
    seeds.update(format_seed_inputs(target))
    if include_fixtures:
        seeds.update(fixture_seed_inputs(target))
    return seeds


def seed_corpus(corpus_dir: Path, target: str, include_fixtures: bool = True) -> int:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, data in seed_inputs(target, include_fixtures).items():
        (corpus_dir / name).write_bytes(data)
        count += 1
    return count


def copy_seed_corpus(seed_dir: Path, target: str, include_fixtures: bool = True) -> int:
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    return seed_corpus(seed_dir, target, include_fixtures)


def dictionary_for(target: str, dict_dir: Path = DICTIONARIES) -> Path | None:
    target_dict = dict_dir / f"{target}.dict"
    if target_dict.exists():
        return target_dict
    all_dict = dict_dir / "all.dict"
    if all_dict.exists():
        return all_dict
    return None
