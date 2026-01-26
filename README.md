# pylibmspack

`pylibmspack` provides in-process Python bindings to **libmspack** for reading and extracting Microsoft CAB, CHM, SZDD, and KWAJ files.

## Install

```bash
pip install pylibmspack
```

Supports Python 3.9+

## Usage

```python
from pylibmspack import CabArchive

cab = CabArchive("example.cab")
print(cab.files())

print(cab.read("hello.txt"))

cab.extract("hello.txt", "./out")

cab.extract_all("./out")
```

### In-memory usage

```python
from pylibmspack import CabArchive

data = open("example.cab", "rb").read()
cab = CabArchive.from_bytes(data)

info = cab.info()
print(info["files_count"], info["flags"])

payload = cab.read("hello.txt")
```

### Safe vs raw extraction

```python
from pylibmspack import CabArchive, CabPathTraversalError

cab = CabArchive("example.cab")
try:
    cab.extract_all("./out", safe=True)
except CabPathTraversalError as exc:
    print("Blocked unsafe path:", exc)

# Raw extraction (no safety checks)
cab.extract_all_raw("./out-raw")
```

### CHM extraction

```python
from pylibmspack import ChmArchive

chm = ChmArchive("manual.chm")
print(chm.info())
print(chm.files())

data = chm.read("index.html")
chm.extract_all("./chm-out")
```

### CHM from bytes

```python
from pylibmspack import ChmArchive

data = open("manual.chm", "rb").read()
chm = ChmArchive.from_bytes(data)
print(chm.files())
```

### SZDD extraction

```python
from pylibmspack import SzddFile

szdd = SzddFile("readme.tx_")
print(szdd.info())

payload = szdd.read()
szdd.extract("./out")
```

### SZDD from bytes

```python
from pylibmspack import SzddFile

data = open("readme.tx_", "rb").read()
szdd = SzddFile.from_bytes(data, name="readme.tx_")
print(szdd.info())
```

### KWAJ extraction

```python
from pylibmspack import KwajFile

kwj = KwajFile("setup.kwj")
print(kwj.info())
data = kwj.read()
kwj.extract("./out")
```

### KWAJ from bytes

```python
from pylibmspack import KwajFile

data = open("setup.kwj", "rb").read()
kwj = KwajFile.from_bytes(data, name="setup.kwj")
print(kwj.info())
```

### Multi-cabinet sets

```python
from pylibmspack import CabArchive

cab = CabArchive("part1.cab")
info = cab.info()

if info["has_next"]:
    print("Next cabinet:", info["next_cabinet"])
    print("Disk label:", info["next_disk"])
```

### FAQ / troubleshooting

**Why do I get `CabPathTraversalError`?**  
The archive contains absolute paths or `..` segments. Use `safe=False` only if you trust the archive contents.

**Can I read from bytes instead of a file path?**  
Yes. Use `CabArchive.from_bytes(data)` and then call `files()`, `read()`, or `info()`.

**Why does extraction fail with `CabDecompressionError`?**  
The CAB may be corrupt, truncated, or uses an unsupported compression method.

## API reference

### CabArchive(path: str)

Open a CAB archive on disk.

### CabArchive.files() -> list[CabFileInfo]

Return metadata for each member as a `CabFileInfo` TypedDict. Each entry includes:

- `name` (str)
- `size` (int)
- `dos_date` (int)
- `dos_time` (int)
- `date_y` / `date_m` / `date_d` (int)
- `time_h` / `time_m` / `time_s` (int)
- `datetime_utc` (str, ISO 8601)
- `attrs` (int)
- `is_readonly` / `is_hidden` / `is_system` / `is_archive` (bool)
- `folder_index` (int)
- `offset` (int)
- `compression` (str: `none`, `mszip`, `quantum`, `lzx`)
- `has_prev` / `has_next` (bool)
- `prev_cabinet` / `next_cabinet` (str | None)
- `cabinet_set_id` / `cabinet_set_index` (int | None)

### CabArchive.read(name: str, *, max_size: int = 256*1024*1024) -> bytes

Extract a member and return its bytes. Enforces a `max_size` limit and uses safe path validation.

### CabArchive.extract(name: str, dest_dir: str, *, safe: bool = True) -> str

Extract a member to disk and return the output path. When `safe=True`, absolute paths and traversal are rejected.

### CabArchive.extract_all(dest_dir: str, *, safe: bool = True) -> list[str]

Extract all members to disk and return output paths.

### CabArchive.extract_raw(name: str, dest_dir: str) -> str

Extract a member using the raw path (no safety checks).

### CabArchive.extract_all_raw(dest_dir: str) -> list[str]

Extract all members using raw paths (no safety checks).

### CabArchive.from_bytes(data: bytes) -> CabArchive

Create an archive backed by in-memory bytes instead of a file path.

### CabArchive.info() -> CabInfo

Return parsed CAB header metadata. The `CabInfo` dict includes:

- `filename` (str | None)
- `base_offset` (int)
- `length` (int)
- `set_id` (int)
- `set_index` (int)
- `header_resv` (int)
- `flags` (int)
- `has_prev` / `has_next` (bool)
- `prev_cabinet` / `next_cabinet` (str | None)
- `prev_disk` / `next_disk` (str | None)
- `files_count` (int)
- `folders_count` (int)

### ChmArchive(path: str)

Open a CHM archive on disk.

### ChmArchive.files(*, include_system: bool = True) -> list[ChmFileInfo]

Return metadata for each member as a `ChmFileInfo` TypedDict. Each entry includes:

- `name` (str)
- `size` (int)
- `offset` (int)
- `section_id` (int)
- `section` (str: `uncompressed`, `mscompressed`, `unknown`)
- `is_system` (bool)

### ChmArchive.read(name: str, *, max_size: int = 256*1024*1024) -> bytes

Extract a member and return its bytes.

### ChmArchive.extract(name: str, dest_dir: str, *, safe: bool = True) -> str

Extract a member to disk and return the output path.

### ChmArchive.extract_all(dest_dir: str, *, safe: bool = True, include_system: bool = True) -> list[str]

Extract all members to disk and return output paths.

### ChmArchive.extract_raw(name: str, dest_dir: str) -> str

Extract a member using the raw path (no safety checks).

### ChmArchive.extract_all_raw(dest_dir: str, *, include_system: bool = True) -> list[str]

Extract all members using raw paths (no safety checks).

### ChmArchive.info() -> ChmInfo

Return parsed CHM header metadata. The `ChmInfo` dict includes:

- `filename` (str | None)
- `length` (int)
- `version` (int)
- `timestamp` (int)
- `language` (int)
- `dir_offset` (int)
- `num_chunks` (int)
- `chunk_size` (int)
- `density` (int)
- `depth` (int)
- `index_root` (int)
- `first_pmgl` (int)
- `last_pmgl` (int)
- `files_count` (int)
- `sysfiles_count` (int)

### ChmArchive.from_bytes(data: bytes) -> ChmArchive

Create an archive backed by in-memory bytes instead of a file path.

### SzddFile(path: str)

Open a SZDD-compressed file on disk.

### SzddFile.info() -> SzddInfo

Return parsed SZDD header metadata. The `SzddInfo` dict includes:

- `format_id` (int)
- `format` (str: `normal`, `qbasic`, `unknown`)
- `length` (int)
- `missing_char` (int)
- `missing_char_str` (str)
- `suggested_name` (str)

### SzddFile.read(*, max_size: int = 256*1024*1024) -> bytes

Decompress and return the file contents.

### SzddFile.extract(dest_dir: str, *, safe: bool = True, out_name: str | None = None) -> str

Decompress to disk and return the output path.

### SzddFile.extract_raw(dest_dir: str, *, out_name: str | None = None) -> str

Decompress using raw (unsafe) path handling.

### SzddFile.from_bytes(data: bytes, *, name: str = "memory.sz_") -> SzddFile

Create a SZDD reader backed by in-memory bytes.

### KwajFile(path: str)

Open a KWAJ-compressed file on disk.

### KwajFile.info() -> KwajInfo

Return parsed KWAJ header metadata. The `KwajInfo` dict includes:

- `comp_type` (int)
- `compression` (str: `none`, `xor`, `szdd`, `lzh`, `mszip`, `unknown`)
- `data_offset` (int)
- `headers` (int)
- `length` (int)
- `filename` (str | None)
- `extra_length` (int)
- `extra` (bytes | None)
- `has_length` / `has_filename` / `has_fileext` / `has_extra` (bool)

### KwajFile.read(*, max_size: int = 256*1024*1024) -> bytes

Decompress and return the file contents.

### KwajFile.extract(dest_dir: str, *, safe: bool = True, out_name: str | None = None) -> str

Decompress to disk and return the output path.

### KwajFile.extract_raw(dest_dir: str, *, out_name: str | None = None) -> str

Decompress using raw (unsafe) path handling.

### KwajFile.from_bytes(data: bytes, *, name: str = "memory.kwj") -> KwajFile

Create a KWAJ reader backed by in-memory bytes.
### Exceptions

All errors derive from `MspackError`:

- `MspackError`
- `MspackFormatError`
- `MspackDecompressionError`
- `MspackPathTraversalError`
- `CabError` / `CabFormatError` / `CabDecompressionError` / `CabPathTraversalError`
- `ChmError` / `ChmFormatError` / `ChmDecompressionError` / `ChmPathTraversalError`
- `SzddError` / `SzddFormatError` / `SzddDecompressionError` / `SzddPathTraversalError`
- `KwajError` / `KwajFormatError` / `KwajDecompressionError` / `KwajPathTraversalError`

## Safe extraction

By default, `extract()` and `extract_all()` reject:
- absolute paths (`/`, `\`, drive letters, UNC paths)
- path traversal (`..` after normalization)
- mixed or odd separators (`/` and `\` are normalized)

Use `safe=False` to allow the original paths.

## Build from source

This project uses setuptools and builds a shared `libmspack` that is bundled into wheels. A pinned libmspack source tarball is included under `pylibmspack/vendor/` and used for offline builds (SHA-256 verified).

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e .
```

If you want to supply a local tarball, pass `--tarball` to `scripts/build_libmspack.py`. To allow a network download during builds, set `PYLIBMSPACK_ALLOW_DOWNLOAD=1` (disabled by default).

## CHM test fixture

The CHM tests use the redistributable fixture at `tests/fixtures/sample.chm`
(NSIS documentation under the zlib/libpng license).

## Licensing

- **pylibmspack** code is MIT licensed.
- Wheels bundle **libmspack** under LGPL-2.1. The corresponding libmspack source tarball is included under `pylibmspack/vendor/`. You may replace the shared library inside `pylibmspack/.libs` with a compatible build.

See `THIRD_PARTY_LICENSES/LGPL-2.1.txt` and `NOTICE` for details.
