#!/usr/bin/env python3
import os
import struct
import time
import zlib

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "tests", "fixtures")

# CAB format constants
CFHEADER_SIZE = 36
CFFOLDER_SIZE = 8
CFFILE_FIXED_SIZE = 16

MSCAB_COMP_NONE = 0x0000
MSCAB_COMP_MSZIP = 0x0001


def dos_datetime(ts):
    t = time.localtime(ts)
    dos_date = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    dos_time = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    return dos_date & 0xFFFF, dos_time & 0xFFFF


def build_cab(files, compression):
    # files: list of (name, data, attrs)
    # Single folder, single CFDATA block
    # Build data stream (concatenate file data)
    data_stream = b"".join(data for _, data, _ in files)

    if compression == "mszip":
        comp_type = MSCAB_COMP_MSZIP
        comp = zlib.compressobj(level=9, wbits=-15)
        comp_data = comp.compress(data_stream) + comp.flush()
        cab_data = b"CK" + comp_data
    elif compression == "none":
        comp_type = MSCAB_COMP_NONE
        cab_data = data_stream
    else:
        raise ValueError("unsupported compression")

    cb_data = len(cab_data)
    cb_uncomp = len(data_stream)

    # Build CFDATA
    cfdata = struct.pack("<IHH", 0, cb_data, cb_uncomp) + cab_data

    # Build CFFOLDER
    coff_cab_start = CFHEADER_SIZE + CFFOLDER_SIZE
    # files section will be placed after folder and data
    cffolder = struct.pack("<IHH", coff_cab_start, 1, comp_type)

    # Build CFFILE entries
    file_entries = b""
    offset = 0
    dos_date, dos_time = dos_datetime(1577836800)  # 2020-01-01
    for name, data, attrs in files:
        file_entries += struct.pack(
            "<IIHHHH",
            len(data),
            offset,
            0,  # folder index
            dos_date,
            dos_time,
            attrs,
        )
        file_entries += name.encode("utf-8") + b"\x00"
        offset += len(data)

    # Header
    coff_files = CFHEADER_SIZE + CFFOLDER_SIZE + len(cfdata)
    cb_cabinet = coff_files + len(file_entries)
    cfiles = len(files)
    cfolders = 1
    flags = 0
    set_id = 0
    i_cab = 0
    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF",
        0,
        cb_cabinet,
        0,
        coff_files,
        0,
        3,
        1,
        cfolders,
        cfiles,
        flags,
        set_id,
        i_cab,
    )

    return header + cffolder + cfdata + file_entries


def write_fixture(name, data):
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote", path)


def main():
    # small_mszip.cab with two files
    files = [
        ("hello.txt", b"hello\n", 0x20),
        ("world.txt", b"world\n", 0x20),
    ]
    cab = build_cab(files, "mszip")
    write_fixture("small_mszip.cab", cab)

    # traversal.cab with a dangerous path
    files = [
        ("../evil.txt", b"evil\n", 0x20),
    ]
    cab = build_cab(files, "none")
    write_fixture("traversal.cab", cab)


if __name__ == "__main__":
    main()
