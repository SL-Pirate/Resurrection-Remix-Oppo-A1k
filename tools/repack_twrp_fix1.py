#!/usr/bin/env python3
"""File-only TWRP fix1 repack. No compilation or device operations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "tools/twrp-fix1"
ORIGINAL = ROOT / "staging/twrp-3.7.0_9-OP486C-bringup1.img"
MAGISKBOOT = ROOT / "tools/magisk-diagnostic/host/magiskboot"
ORIGINAL_SHA256 = "a35e5ef1b7e9518068446fe3d771de0e2787b1e8bcbf01b57db89767dc0fcdba"
SALT = "e7407675f9eb4d31f1150d3b9527566d2a65092dd15132c13eea4a836ac58cbf"
PARTITION_SIZE = 33554432


def digest(data):
    return hashlib.sha256(data).hexdigest()


def header(data):
    assert data[:8] == b"ANDROID!"
    fields = ["kernel_size", "kernel_address", "ramdisk_size", "ramdisk_address",
              "second_size", "second_address", "tags_address", "page_size",
              "header_version", "os_version_encoded"]
    result = dict(zip(fields, struct.unpack_from("<10I", data, 8)))
    result["name"] = data[48:64].hex()
    result["cmdline_bytes"] = (data[64:576] + data[608:1632]).hex()
    result["image_id"] = data[576:608].hex()
    (result["recovery_dtbo_size"], result["recovery_dtbo_offset"],
     result["header_size"]) = struct.unpack_from("<IQI", data, 1632)
    return result


def cpio_entries(path):
    data = path.read_bytes()
    offset = 0
    entries = {}
    while True:
        assert data[offset:offset + 6] in (b"070701", b"070702")
        values = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        name = data[offset + 110:offset + 110 + values[11]]
        assert name.endswith(b"\0")
        name = name[:-1].decode()
        offset = (offset + 110 + values[11] + 3) & ~3
        content = data[offset:offset + values[6]]
        assert len(content) == values[6]
        offset = (offset + values[6] + 3) & ~3
        if name == "TRAILER!!!":
            break
        assert name not in entries
        entries[name] = {"mode": values[1], "uid": values[2], "gid": values[3],
                         "rdevmajor": values[9], "rdevminor": values[10],
                         "size": values[6], "sha256": digest(content)}
    assert not any(data[offset:])
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "staging/twrp-3.7.0_9-OP486C-bringup1-fix1.img")
    parser.add_argument("--work-dir", type=Path, default=INPUTS / "repack-work")
    parser.add_argument("--report", type=Path, default=ROOT / "evidence/twrp-fix1-verification.json")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    output = args.output.resolve()
    if output.exists() or args.report.exists():
        raise SystemExit("Refusing to overwrite existing output or report")
    original = ORIGINAL.read_bytes()
    assert digest(original) == ORIGINAL_SHA256
    inputs = json.loads((INPUTS / "inputs.json").read_text())
    for name, expected in inputs.items():
        assert digest((INPUTS / name).read_bytes()) == expected
    work.mkdir(parents=True, exist_ok=False)
    log = []

    def run(command, directory=work):
        result = subprocess.run(command, cwd=directory, capture_output=True, text=True)
        log.append("COMMAND " + repr(command) + "\n" + result.stdout + result.stderr)
        (work / "repack.log").write_text("\n".join(log))
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout + result.stderr

    def avb(*arguments):
        return run(["podman", "run", "--rm", "--network=none", "--security-opt", "label=disable",
                    "-v", str(work) + ":/work:rw",
                    "-v", str(INPUTS / "avbtool-v1.1.0.py") + ":/avbtool:ro",
                    "localhost/oppo-a1k-twrp9:local", "python2", "/avbtool", *arguments])

    shutil.copyfile(ORIGINAL, work / "base.img")
    avb("erase_footer", "--image", "/work/base.img")
    run([str(MAGISKBOOT), "unpack", "base.img"])
    before = cpio_entries(work / "ramdisk.cpio")
    shutil.copyfile(work / "ramdisk.cpio", work / "ramdisk-original.cpio")
    for name in ["recovery.fstab", "libtwrpmtp-ffs.so"]:
        shutil.copyfile(INPUTS / name, work / name)
    assert before["etc/recovery.fstab"]["mode"] == 0o100644
    assert before["sbin/libtwrpmtp-ffs.so"]["mode"] == 0o100750
    run([str(MAGISKBOOT), "cpio", "ramdisk.cpio",
         "add 0644 etc/recovery.fstab recovery.fstab",
         "add 0750 sbin/libtwrpmtp-ffs.so libtwrpmtp-ffs.so"])
    # With no replacement kernel file, magiskboot retains the original
    # compressed kernel instead of recompressing an unchanged kernel.
    (work / "kernel").rename(work / "kernel-unpacked-original")
    run([str(MAGISKBOOT), "repack", "base.img", "new.img"])
    avb("add_hash_footer", "--image", "/work/new.img", "--partition_name", "recovery",
        "--partition_size", str(PARTITION_SIZE), "--algorithm", "NONE", "--salt", SALT)
    avb_info = avb("info_image", "--image", "/work/new.img")
    # avbtool 1.1.0 resolves the hash descriptor using partition_name.img.
    (work / "recovery.img").symlink_to("new.img")
    avb_verified = avb("verify_image", "--image", "/work/new.img")
    verified_dir = work / "verify"
    verified_dir.mkdir()
    run([str(MAGISKBOOT), "unpack", str(work / "new.img")], verified_dir)
    after = cpio_entries(verified_dir / "ramdisk.cpio")
    assert set(before) == set(after)
    changed = [name for name in before if before[name] != after[name]]
    assert set(changed) == {"etc/recovery.fstab", "sbin/libtwrpmtp-ffs.so"}
    for name, source in [("etc/recovery.fstab", "recovery.fstab"),
                         ("sbin/libtwrpmtp-ffs.so", "libtwrpmtp-ffs.so")]:
        assert after[name]["sha256"] == inputs[source]
        for field in ["mode", "uid", "gid", "rdevmajor", "rdevminor"]:
            assert before[name][field] == after[name][field]
    candidate = (work / "new.img").read_bytes()
    old_h, new_h = header(original), header(candidate)
    differences = {name: {"original": old_h[name], "fix1": new_h[name]}
                   for name in old_h if old_h[name] != new_h[name]}
    assert set(differences) <= {"ramdisk_size", "image_id", "recovery_dtbo_offset"}
    old_kernel = original[old_h["page_size"]:old_h["page_size"] + old_h["kernel_size"]]
    new_kernel = candidate[new_h["page_size"]:new_h["page_size"] + new_h["kernel_size"]]
    assert old_kernel == new_kernel
    old_dtbo = original[old_h["recovery_dtbo_offset"]:old_h["recovery_dtbo_offset"] + old_h["recovery_dtbo_size"]]
    new_dtbo = candidate[new_h["recovery_dtbo_offset"]:new_h["recovery_dtbo_offset"] + new_h["recovery_dtbo_size"]]
    assert old_dtbo == new_dtbo
    assert (work / "kernel_dtb").read_bytes() == (verified_dir / "kernel_dtb").read_bytes()
    assert len(candidate) == PARTITION_SIZE and candidate[-64:-60] == b"AVBf"
    assert "Algorithm:                NONE" in avb_info
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(candidate)
    report = {
        "result": "passed: file-only fix1 image repack and verification",
        "revision": "fix1", "embedded_twrp_version_unchanged": "3.7.0_9 OP486C-bringup1",
        "image": str(output), "size": len(candidate), "sha256": digest(candidate),
        "original_image": str(ORIGINAL), "original_sha256": ORIGINAL_SHA256,
        "header_changes": differences, "other_header_fields_unchanged": True,
        "compressed_kernel_identical": True, "compressed_kernel_sha256": digest(new_kernel),
        "kernel_dtb_identical": True, "recovery_dtbo_identical": True,
        "recovery_dtbo_sha256": digest(new_dtbo),
        "ramdisk_entry_count": len(after), "added_entries": [], "removed_entries": [],
        "changed_entries": {name: {"original": before[name], "fix1": after[name]} for name in changed},
        "avb": {"algorithm": "NONE", "salt": SALT, "regenerated": True,
                "hash_verification_passed": True, "info": avb_info, "verification": avb_verified},
        "inputs": inputs, "magiskboot_sha256": digest(MAGISKBOOT.read_bytes()),
        "repack_script": str(Path(__file__).resolve()), "repack_log": str(work / "repack.log"),
        "device_operations": False, "compiled_locally": False, "boot_tested": False,
        "limitations": ["Only static image checks were performed here.",
                        "Unsigned AVB does not establish OEM signature acceptance.",
                        "The original bring-up encrypted-data limitation remains."]}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["result", "image", "size", "sha256", "ramdisk_entry_count"]}, indent=2))


if __name__ == "__main__":
    main()
