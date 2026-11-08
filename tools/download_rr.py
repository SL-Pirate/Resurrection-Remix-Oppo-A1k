#!/usr/bin/env python3
"""Resume the selected upstream RR GSI in checked HTTP ranges, then test XZ."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import fcntl
import hashlib
import json
import shutil
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = ("https://downloads.sourceforge.net/project/resurrection-remix-q-gsi/"
       "compressed/system-arm64-ab-vanilla-nosu-userdebug.img.xz")
# Content-Length and Last-Modified observed on the maintainer's download server.
TOTAL = 818972692
CHUNK = 16 * 1024 * 1024
NAME = "RR-8.7.3-system-arm64-ab-vanilla-nosu-userdebug.img.xz"
CACHE = ROOT / "downloads/rr-chunks"
DEST = ROOT / "downloads" / NAME


def fetch(index):
    start, end = index * CHUNK, min((index + 1) * CHUNK, TOTAL) - 1
    size = end - start + 1
    chunk = CACHE / f"{index:03d}.bin"
    if chunk.exists() and chunk.stat().st_size == size:
        return chunk
    partial = chunk.with_suffix(".part")
    for attempt in range(8):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > size:
            raise RuntimeError(f"Oversized partial chunk: {partial}")
        if offset == size:
            partial.replace(chunk)
            return chunk
        request = urllib.request.Request(URL, headers={
            "Range": f"bytes={start + offset}-{end}",
            "Accept-Encoding": "identity",
            "User-Agent": "oppo-a1k-porting/1.0",
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                expected = f"bytes {start + offset}-{end}/{TOTAL}"
                if response.status != 206 or response.headers.get("Content-Range") != expected:
                    raise RuntimeError(f"Unexpected range response: {dict(response.headers)}")
                with partial.open("ab") as output:
                    while data := response.read(min(1024 * 1024, size - offset)):
                        output.write(data)
                        offset += len(data)
                        if offset == size:
                            break
            if offset != size:
                raise RuntimeError(f"Truncated range {index}: {offset}/{size}")
            partial.replace(chunk)
            return chunk
        except Exception as exc:
            print(f"Range {index}: attempt {attempt + 1} failed: {exc}", flush=True)
            if attempt == 7:
                raise
            time.sleep(min(2 ** attempt, 15))


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if DEST.exists():
            raise SystemExit(f"Output already exists: {DEST}")
        # Reuse only complete ranges from the interrupted sequential transfer.
        previous = DEST.with_suffix(DEST.suffix + ".part")
        if previous.exists():
            with previous.open("rb") as source:
                for index in range(previous.stat().st_size // CHUNK):
                    chunk = CACHE / f"{index:03d}.bin"
                    data = source.read(CHUNK)
                    if not chunk.exists():
                        chunk.write_bytes(data)
        count = (TOTAL + CHUNK - 1) // CHUNK
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fetch, index) for index in range(count)]
            for complete, future in enumerate(as_completed(futures), 1):
                future.result()
                print(f"Completed {complete}/{count} ranges", flush=True)
        assembled = CACHE / "assembled.img.xz"
        with assembled.open("wb") as output:
            for index in range(count):
                with (CACHE / f"{index:03d}.bin").open("rb") as source:
                    shutil.copyfileobj(source, output)
        assert assembled.stat().st_size == TOTAL
        subprocess.run(["xz", "--test", str(assembled)], check=True)
        digest = hashlib.file_digest(assembled.open("rb"), "sha256").hexdigest()
        assembled.replace(DEST)
        (ROOT / "evidence/rr-download.json").write_text(json.dumps({
            "url": URL, "size": TOTAL, "sha256": digest,
            "xz_integrity": "passed", "publisher_hash_verified": False,
        }, indent=2) + "\n")
        print(f"Downloaded and XZ-tested: {DEST}\nSHA-256: {digest}", flush=True)


if __name__ == "__main__":
    main()
