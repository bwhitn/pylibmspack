from __future__ import annotations

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    libs = Path(__file__).resolve().parent / ".libs"
    if libs.is_dir():
        os.add_dll_directory(str(libs))
