"""Prepara el paquete de Lambda para Linux usando solo wheels de Python puro."""

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "build" / "package"
if TARGET.exists():
    shutil.rmtree(TARGET)
TARGET.mkdir(parents=True)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--requirement",
        str(ROOT / "requirements.txt"),
        "--target",
        str(TARGET),
        "--platform",
        "manylinux2014_x86_64",
        "--implementation",
        "cp",
        "--python-version",
        "3.12",
        "--only-binary=:all:",
        "--no-compile",
        "--disable-pip-version-check",
    ],
    check=True,
)
shutil.copy2(ROOT / "src" / "handler.py", TARGET / "handler.py")
print(f"Paquete listo en: {TARGET}")
