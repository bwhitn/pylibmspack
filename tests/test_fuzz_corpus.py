import zipfile

from fuzz.corpus import dictionary_for, oab_patch_pair, seed_corpus, seed_inputs
from scripts.export_fuzz_artifacts import copy_dictionary, write_options, write_seed_corpus


def test_all_target_seeds_route_to_native_selector_bytes():
    seeds = seed_inputs("all", include_fixtures=False)

    assert seeds["cab_cab_magic"].startswith(b"\x00MSCF")
    assert seeds["chm_chm_magic"].startswith(b"\x01ITSF")
    assert seeds["szdd_szdd_magic"].startswith(b"\x02SZDD")
    assert seeds["kwaj_kwaj_magic"].startswith(b"\x03KWAJ")
    assert seeds["hlp_hlp_literal_stream"].startswith(b"\x04")
    assert seeds["oab_oab_full"].startswith(b"\x05")
    assert seeds["oab_patch_oab_patch_pair"].startswith(b"\x06")


def test_oab_patch_pair_splits_into_patch_and_base_halves():
    payload = oab_patch_pair()
    split = len(payload) // 2

    assert len(payload) % 2 == 0
    assert payload[:4] == b"\x03\x00\x00\x00"
    assert payload[split:].startswith(b"base")


def test_seed_corpus_writes_target_seeds(tmp_path):
    corpus_dir = tmp_path / "cab"

    count = seed_corpus(corpus_dir, "cab", include_fixtures=False)

    assert count > 0
    assert (corpus_dir / "cab_magic").read_bytes() == b"MSCF"


def test_dictionary_for_uses_specific_dictionary():
    dictionary = dictionary_for("cab")

    assert dictionary is not None
    assert dictionary.name == "cab.dict"


def test_export_fuzz_artifacts_use_oss_fuzz_filenames(tmp_path):
    copy_dictionary(tmp_path, "cab")
    write_options(tmp_path, "cab", max_len=4096, timeout=10, rss_limit_mb=1024)
    write_seed_corpus(tmp_path, "cab", include_fixtures=False)

    assert (tmp_path / "pylibmspack_fuzz_cab.dict").exists()
    assert (
        "dict = pylibmspack_fuzz_cab.dict"
        in (tmp_path / "pylibmspack_fuzz_cab.options").read_text()
    )

    with zipfile.ZipFile(tmp_path / "pylibmspack_fuzz_cab_seed_corpus.zip") as zf:
        assert "cab_magic" in zf.namelist()
        assert zf.read("cab_magic") == b"MSCF"
