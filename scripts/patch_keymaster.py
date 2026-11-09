#!/usr/bin/env python3
"""Patch the exact tested VNDK28 library without modifying the input or device."""
import hashlib
from pathlib import Path
import sys

ORIGINAL = "338a4e6ceb00f5f8d30bb77013a6d2c7748c53e00eba1a1d7917c28a180f8c89"
PATCHED = "ee61b394cf60807faf7369ac529d9363355e4e1c88b10a58dccfcbb4d860f560"
if len(sys.argv) != 3:
    raise SystemExit("Usage: patch_keymaster.py ORIGINAL_LIBRARY NEW_OUTPUT")
data = Path(sys.argv[1]).read_bytes()
if hashlib.sha256(data).hexdigest() != ORIGINAL:
    raise SystemExit("Unexpected input library; refusing to patch")
for old, new in [
    (b"ro.build.version.release", b"ro.keymaster.xxx.release"),
    (b"ro.build.version.security_patch", b"ro.keymaster.xxx.security_patch"),
]:
    if len(old) != len(new) or data.count(old) != 1:
        raise SystemExit("Unexpected property layout")
    data = data.replace(old, new)
if hashlib.sha256(data).hexdigest() != PATCHED:
    raise SystemExit("Output verification failed")
with Path(sys.argv[2]).open("xb") as output:
    output.write(data)
print("Verified patched library:", PATCHED)
