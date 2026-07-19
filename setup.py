from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts" / "build_libmspack.py"


class BuildExt(build_ext):
    def run(self):
        self._build_libmspack()
        super().run()
        self._bundle_libmspack()

    def _build_libmspack(self):
        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)
        out_dir = build_temp / "libmspack-out"
        src_dir = build_temp / "libmspack-src"
        info_path = build_temp / "libmspack-build.json"

        cmd = [
            sys.executable,
            str(SCRIPT),
            "--out-dir",
            str(out_dir),
            "--src-dir",
            str(src_dir),
            "--json-out",
            str(info_path),
        ]
        env = os.environ.copy()
        env.setdefault("PYLIBMSPACK_LIBMSPACK_VERSION", "0.11")
        subprocess.check_call(cmd, env=env)

        with info_path.open("r", encoding="utf-8") as f:
            info = json.load(f)
        self._libmspack_info = info

        for ext in self.extensions:
            ext.include_dirs.append(info["include_dir"])
            ext.library_dirs.append(info["lib_dir"])
            ext.libraries.append(info["library_name"])
            if not sys.platform.startswith("win"):
                ext.extra_link_args.append(info["shared_lib"])

            if sys.platform.startswith("linux"):
                ext.extra_link_args.append("-Wl,-rpath,$ORIGIN/.libs")
            elif sys.platform == "darwin":
                ext.extra_link_args.append("-Wl,-rpath,@loader_path/.libs")

    def _bundle_libmspack(self):
        info = getattr(self, "_libmspack_info", None)
        if not info:
            return
        shared_lib = Path(info["shared_lib"])
        if not shared_lib.exists():
            return

        package_dirs = {Path(self.build_lib) / "pylibmspack"}
        if self.inplace:
            package_dirs.update(
                Path(self.get_ext_fullpath(ext.name)).resolve().parent for ext in self.extensions
            )

        for package_dir in package_dirs:
            self._copy_libmspack(shared_lib, package_dir)

    def _copy_libmspack(self, shared_lib: Path, package_dir: Path) -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        pkg_libs = package_dir / ".libs"
        pkg_libs.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shared_lib, pkg_libs / shared_lib.name)
        if sys.platform == "darwin":
            pkg_dylibs = package_dir / ".dylibs"
            pkg_dylibs.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shared_lib, pkg_dylibs / shared_lib.name)
            shutil.copy2(shared_lib, package_dir / shared_lib.name)


ext_modules = [
    Extension(
        "pylibmspack._cab",
        sources=["src/pylibmspack/_cab.c"],
        include_dirs=[],
        libraries=[],
        library_dirs=[],
        extra_link_args=[],
    )
]

setup(cmdclass={"build_ext": BuildExt}, ext_modules=ext_modules)
