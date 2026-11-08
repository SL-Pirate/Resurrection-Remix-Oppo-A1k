#!/usr/bin/env python3
"""Apply the consolidated patch to a clean, pinned LK checkout; never builds/flashes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2:
    raise SystemExit('Usage: prepare_lk.py PATH_TO_CLEAN_LK_CHECKOUT')
root = Path(sys.argv[1]).resolve()
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
expected = json.loads((repo / 'manifests/lk-provenance.json').read_text())['base_commit']
if git('rev-parse', 'HEAD') != expected:
    raise SystemExit('Wrong upstream revision; refusing to modify checkout.')
if git('status', '--porcelain'):
    raise SystemExit('Checkout is not clean; refusing to overwrite changes.')
patch = repo / 'patches/lk/0001-op486c-tested-port.patch'
git('apply', '--check', str(patch))
git('apply', str(patch))
for rel, target in json.loads((repo / 'manifests/lk-toolchain-symlinks.json').read_text()).items():
    p = root / rel
    resolved = (p.parent / target).resolve()
    if not resolved.is_relative_to(root):
        raise SystemExit('Symlink escapes source root: ' + rel)
    if p.is_symlink():
        p.unlink()
    elif p.exists():
        raise SystemExit('Refusing to replace regular file with symlink: ' + rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.symlink_to(target)
for rel, expected_hash in json.loads((repo / 'manifests/lk-source-sha256.json').read_text()).items():
    if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected_hash:
        raise SystemExit('Source mismatch: ' + rel)
print('Applied final LK patch and verified source hashes. No compilation or device writes.')
