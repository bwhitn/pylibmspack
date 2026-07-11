from pathlib import Path

import pytest

from pylibmspack import HlpError, HlpFile, HlpFormatError, HlpPathTraversalError


def _mshelp_literals(payload: bytes) -> bytes:
    chunks = []
    for idx in range(0, len(payload), 8):
        # In MS Help mode, the control byte is inverted before bit checks.
        # A zero control byte therefore marks up to eight following bytes as literals.
        chunks.append(b"\x00" + payload[idx : idx + 8])
    return b"".join(chunks)


def test_hlp_read_and_extract(tmp_path):
    payload = b"MS Help LZSS payload\n"
    stream = _mshelp_literals(payload)
    path = tmp_path / "sample.hlp"
    path.write_bytes(stream)

    hlp = HlpFile(str(path))

    assert hlp.read() == payload
    out_path = hlp.extract(str(tmp_path / "out"), out_name="sample.txt")
    assert Path(out_path).read_bytes() == payload


def test_hlp_from_bytes():
    payload = b"from memory"

    hlp = HlpFile.from_bytes(_mshelp_literals(payload), name="sample.hlp")

    assert hlp.suggested_name() == "sample.hlp"
    assert hlp.read() == payload


def test_hlp_max_size():
    hlp = HlpFile.from_bytes(_mshelp_literals(b"too large"))

    with pytest.raises(HlpError):
        hlp.read(max_size=1)


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "..\\evil.txt",
        "/../evil.txt",
        "C:\\evil.txt",
        "\\\\server\\share\\evil.txt",
    ],
)
def test_hlp_safe_extract_blocks_traversal(tmp_path, name):
    hlp = HlpFile.from_bytes(_mshelp_literals(b"payload"))

    with pytest.raises(HlpPathTraversalError):
        hlp.extract(str(tmp_path), out_name=name, safe=True)


def test_hlp_rejects_full_winhelp_container_magic():
    hlp = HlpFile.from_bytes(b"?_\x03\x00not-a-raw-stream")

    with pytest.raises(HlpFormatError, match="full WinHelp"):
        hlp.read()
