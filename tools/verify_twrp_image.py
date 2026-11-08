#!/usr/bin/env python3
"""Check the locally built OP486C recovery against its captured stock layout."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/mkbootimg"))
from unpack_bootimg import unpack_bootimg


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cpio_members(data):
    """Read a newc archive without extracting any paths onto the filesystem."""
    entries = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError(f"Invalid newc header at {offset}")
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        offset += 110
        name_bytes = data[offset:offset + namesize]
        if len(name_bytes) != namesize or not name_bytes.endswith(b"\0"):
            raise ValueError("Truncated cpio name")
        name = name_bytes[:-1].decode()
        offset = (offset + namesize + 3) & ~3
        if name == "TRAILER!!!":
            return entries
        content = data[offset:offset + size]
        if len(content) != size:
            raise ValueError(f"Truncated cpio member {name}")
        name = name.removeprefix("./")
        if name in entries:
            raise ValueError(f"Duplicate cpio member {name}")
        entries[name] = {"mode": mode, "content": content}
        offset = (offset + size + 3) & ~3
    raise ValueError("Missing cpio trailer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "evidence/twrp-image-verification.json")
    args = parser.parse_args()
    candidate = args.image.resolve()
    raw = candidate.read_bytes()
    layout = json.loads((ROOT / "evidence/partitions.json").read_text())
    checks = {}
    checks["fits_recovery_partition"] = 0 < len(raw) <= layout["recovery"]["size"]
    with tempfile.TemporaryDirectory(prefix="op486c-verify-") as temporary:
        temporary = Path(temporary)
        original_dir, candidate_dir = temporary / "stock", temporary / "candidate"
        original = unpack_bootimg(str(ROOT / "stock/partitions/recovery.img"), str(original_dir))
        info = unpack_bootimg(str(candidate), str(candidate_dir))
        fields = ["header_version", "page_size", "kernel_load_address",
                  "ramdisk_load_address", "second_load_address", "tags_load_address",
                  "second_size", "os_version", "os_patch_level",
                  "extra_cmdline", "boot_header_size"]
        header = {key: getattr(info, key) for key in fields}
        for key in fields:
            checks[f"stock_header_{key}"] = getattr(info, key) == getattr(original, key)
        # Preserve stock boot options; recovery intentionally uses an eng build.
        # build/make/core/Makefile appends this token automatically.
        expected_cmdline = " ".join(token for token in original.cmdline.split()
                                    if not token.startswith("buildvariant=")) + " buildvariant=eng"
        header["cmdline"] = info.cmdline
        checks["recovery_cmdline_matches_intended_build"] = info.cmdline == expected_cmdline
        for name in ("kernel", "recovery_dtbo"):
            checks[f"stock_{name}_identical"] = ((original_dir / name).read_bytes()
                                                  == (candidate_dir / name).read_bytes())
        ramdisk = gzip.decompress((candidate_dir / "ramdisk").read_bytes())
        entries = cpio_members(ramdisk)
        for name in ("init", "sbin/recovery", "sbin/adbd"):
            content = entries.get(name, {}).get("content", b"")
            checks[f"{name}_aarch64_elf"] = (content[:5] == b"\x7fELF\x02"
                                              and len(content) >= 20
                                              and struct.unpack_from("<H", content, 18)[0] == 183)
        tree = ROOT / "device/oppo/OP486C"
        for name, source in {"etc/recovery.fstab": tree / "recovery.fstab",
                             "init.recovery.usb.rc": tree / "recovery/root/init.recovery.usb.rc"}.items():
            checks[f"{name}_matches_tree"] = entries.get(name, {}).get("content") == source.read_bytes()
        props = {}
        for line in entries.get("prop.default", {}).get("content", b"").decode().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                props[key] = value
        for key, value in {"ro.product.device": "OP486C", "ro.product.model": "CPH1923",
                           "ro.debuggable": "1", "ro.secure": "0"}.items():
            checks[f"property_{key}"] = props.get(key) == value
        checks["avb_footer_present"] = raw[-64:-60] == b"AVBf"
        report = {"image": str(candidate), "size": len(raw), "sha256": sha(raw),
                  "header": header, "ramdisk_bytes": len(ramdisk),
                  "ramdisk_member_count": len(entries), "checks": checks,
                  "result": "passed" if all(checks.values()) else "failed",
                  "boot_tested": False,
                  "limitations": ["Static artifact checks do not prove bootability or hardware operation.",
                                  "Initial bring-up does not support encrypted data decryption."]}
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        if not all(checks.values()):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
