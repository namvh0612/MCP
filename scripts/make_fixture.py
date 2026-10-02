"""Copy an EAE solution into a test fixture, stripping build output and security material.

Usage: python scripts/make_fixture.py <source_solution_dir> <dest_dir>
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Directory names removed wherever they appear.
EXCLUDED_DIRS = {"bin", "obj", "SnapshotCompiles", "Security", "Certificates", ".vs", "PluginData", "ExternLibraries"}
# Binary or bulky files that the server never parses.
EXCLUDED_SUFFIXES = {".zip", ".dll", ".exe", ".pdb", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".db"}
# .resx files above this size only embed images.
MAX_RESX_BYTES = 128 * 1024
# Paths (relative, forward slashes) removed exactly.
EXCLUDED_PREFIXES = ("Topology/Content",)
EXCLUDED_FILES = {"se-rbac-users.json", "se-rbac-roles.json"}


def keep(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return False
    if rel.name in EXCLUDED_FILES or rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    posix = rel.as_posix()
    return not any(posix.startswith(p) for p in EXCLUDED_PREFIXES)


def make_fixture(src: Path, dst: Path) -> tuple[int, int]:
    copied = skipped = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if not keep(rel) or (path.suffix.lower() == ".resx" and path.stat().st_size > MAX_RESX_BYTES):
            skipped += 1
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied, skipped


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    c, s = make_fixture(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"copied {c} files, skipped {s}")
