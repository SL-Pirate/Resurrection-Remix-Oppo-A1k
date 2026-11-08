#!/usr/bin/env python3
"""Repack verified combined fix1 with tested no-FBE assets and no boot logger.

File-only operation. Requires existing host magiskboot and the existing local
Python2 container for avbtool; does not compile or access a connected device.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repack_twrp_fix1 import ROOT, MAGISKBOOT, INPUTS, PARTITION_SIZE, header, cpio_entries, digest
from verify_finalize_twrp_magisk_fix1 import avb_hash, contents

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'assets'
SOURCE = ROOT / 'staging/magisk-31.1-twrp-OP486C-fix1-experimental.img'
TESTED = ROOT / 'staging/magisk-31.1-twrp-OP486C-diag2-nofbe.img'
EXPECTED = {
    'busybox': '4d60ab3f5a59ebb2ca863f2f514e6924401b581e9b64f602665c008177626651',
    'no-fbe.sh': '787b5c38ccbc2319c9bed6ebd424d6120d218a1bc44821e5469982fcbf46fed6',
    'op486c-no-fbe.rc': '56ea2d628858a4e82c278b74d875dc89407529f69ac17ad4379a5db0924b1ac6',
    'fstab.no-fbe': '1eee595a427b920d6fee95392664b3b79ffd492c67122fa4279897780d15d552',
}
FILES = {
    'overlay.d/op486c-no-fbe.rc': ('0644', 'op486c-no-fbe.rc'),
    'overlay.d/sbin/op486c-bootdiag/busybox': ('0750', 'busybox'),
    'overlay.d/sbin/op486c-bootdiag/no-fbe.sh': ('0750', 'no-fbe.sh'),
    'overlay.d/sbin/op486c-bootdiag/fstab.no-fbe': ('0644', 'fstab.no-fbe'),
}
DIRECTORY = 'overlay.d/sbin/op486c-bootdiag'
LOGGER = {'overlay.d/op486c-bootdiag.rc', 'overlay.d/sbin/op486c-bootdiag/logger.sh'}


def full_entries(path):
    """Record every newc header field, filename and content for stronger comparison."""
    data, offset, entries = path.read_bytes(), 0, {}
    while True:
        assert data[offset:offset + 6] == b'070701'
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        name = data[offset + 110:offset + 109 + fields[11]].decode()
        offset = (offset + 110 + fields[11] + 3) & ~3
        content = data[offset:offset + fields[6]]
        offset = (offset + fields[6] + 3) & ~3
        if name == 'TRAILER!!!':
            assert not any(data[offset:])
            return entries
        assert name not in entries
        entries[name] = {'header_fields': fields, 'content_sha256': digest(content)}


def retained_equal(before, after):
    """magiskboot renumbers archive inode IDs; there are no hardlink groups."""
    renumbered = 0
    for name, value in before.items():
        other = after[name]
        assert value['header_fields'][4] <= 1 and other['header_fields'][4] <= 1
        assert value['header_fields'][1:] == other['header_fields'][1:], name
        assert value['content_sha256'] == other['content_sha256'], name
        renumbered += value['header_fields'][0] != other['header_fields'][0]
    return renumbered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=HERE / 'repack')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'staging/magisk-31.1-twrp-OP486C-nofbe-fix1.img')
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'evidence/twrp-magisk-nofbe-fix1-verification.json')
    args = parser.parse_args()
    work, output, report_path = args.work_dir.resolve(), args.output.resolve(), args.report.resolve()
    assert not any(p.exists() for p in [work, output, report_path]), 'Refusing to overwrite artifacts'
    original, tested = SOURCE.read_bytes(), TESTED.read_bytes()
    assert digest(original) == 'd9afeae649348cfeb81bd48dbde266c5de8f328cfd5c268a21a4ed607c040e12'
    assert digest(tested) == 'fb579b1aa0c678dff7a2651cdc42eaeb8eaa0e9181103d185d6cf0769a576707'
    assert digest(MAGISKBOOT.read_bytes()) == 'd7e69a2891a5a1ee3151347403e6d0e21bb097864363d48d366bdfefd931b052'
    for name, expected in EXPECTED.items():
        assert digest((ASSETS / name).read_bytes()) == expected, name
    apk = ROOT / 'downloads/Magisk-v31.1.apk'
    assert digest(apk.read_bytes()) == '89cefac0a318afa39fb3880c45c87b036c05bc1ebf02a7a715b7f8d7c26ac6e7'
    with zipfile.ZipFile(apk) as z:
        assert z.read('lib/arm64-v8a/libbusybox.so') == (ASSETS / 'busybox').read_bytes()
    work.mkdir(parents=True)
    logs = []

    def run(cmd, cwd=work):
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        logs.append(repr(cmd) + '\n' + result.stdout + result.stderr)
        (work / 'repack.log').write_text('\n'.join(logs))
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout + result.stderr

    def avb(*argv):
        return run(['podman', 'run', '--rm', '--network=none', '--security-opt', 'label=disable',
                    '-v', str(work) + ':/work:rw', '-v', str(INPUTS / 'avbtool-v1.1.0.py') + ':/avbtool:ro',
                    'localhost/oppo-a1k-twrp9:local', 'python2', '/avbtool', *argv])

    shutil.copyfile(SOURCE, work / 'base.img')
    avb('erase_footer', '--image', '/work/base.img')
    assert (work / 'base.img').read_bytes() == original[:avb_hash(original)['original_image_size']]
    run([str(MAGISKBOOT), 'unpack', 'base.img'])
    before, full_before = cpio_entries(work / 'ramdisk.cpio'), full_entries(work / 'ramdisk.cpio')
    shutil.copyfile(work / 'ramdisk.cpio', work / 'original.cpio')
    assert not (set(before) & (set(FILES) | {DIRECTORY} | LOGGER))
    additions = [f'mkdir 0750 {DIRECTORY}']
    for target, (mode, name) in FILES.items():
        shutil.copyfile(ASSETS / name, work / name)
        additions.append(f'add {mode} {target} {name}')
    run([str(MAGISKBOOT), 'cpio', 'ramdisk.cpio', *additions])
    # Preserve the exact compressed kernel by not supplying a replacement kernel.
    (work / 'kernel').rename(work / 'kernel-original')
    run([str(MAGISKBOOT), 'repack', 'base.img', 'recovery.img'])
    payload = (work / 'recovery.img').read_bytes()
    avb('add_hash_footer', '--image', '/work/recovery.img', '--partition_name', 'recovery',
        '--partition_size', str(PARTITION_SIZE), '--algorithm', 'NONE', '--salt', avb_hash(original)['salt'])
    avb_result = avb('verify_image', '--image', '/work/recovery.img')
    verify = work / 'verify'; verify.mkdir()
    run([str(MAGISKBOOT), 'unpack', str(work / 'recovery.img')], verify)
    after, full_after = cpio_entries(verify / 'ramdisk.cpio'), full_entries(verify / 'ramdisk.cpio')
    assert set(after) - set(before) == set(FILES) | {DIRECTORY}
    assert all(after[n] == v for n, v in before.items())
    renumbered_from_base = retained_equal(full_before, full_after)
    for target, (mode, name) in FILES.items():
        assert after[target]['sha256'] == EXPECTED[name]
        assert after[target]['mode'] == 0o100000 + int(mode, 8)
        assert after[target]['uid'] == after[target]['gid'] == 0
    assert not (set(after) & LOGGER)
    # Independently unpack the boot-tested diagnostic image, proving that this
    # ramdisk is exactly the tested one with the two logging entries removed.
    diag = work / 'tested-diag2'; diag.mkdir()
    run([str(MAGISKBOOT), 'unpack', str(TESTED)], diag)
    dm, df = cpio_entries(diag / 'ramdisk.cpio'), full_entries(diag / 'ramdisk.cpio')
    assert set(dm) - set(after) == LOGGER and not (set(after) - set(dm))
    assert all(dm[n] == v for n, v in after.items())
    renumbered_from_diag = retained_equal(full_after, df)
    final = (work / 'recovery.img').read_bytes()
    old, new = header(original), header(final)
    changes = {k: {'base': old[k], 'nofbe_fix1': new[k]} for k in old if old[k] != new[k]}
    assert set(changes) <= {'ramdisk_size', 'recovery_dtbo_offset', 'image_id'}
    kernel = final[new['page_size']:new['page_size'] + new['kernel_size']]
    assert kernel == original[old['page_size']:old['page_size'] + old['kernel_size']]
    for name in ['kernel_dtb', 'recovery_dtbo']:
        assert (work / name).read_bytes() == (verify / name).read_bytes() == (diag / name).read_bytes()
    assert (work / 'kernel-original').read_bytes() == (verify / 'kernel').read_bytes() == (diag / 'kernel').read_bytes()
    footer = avb_hash(final)
    assert footer['hash_matches'] and footer['image_size_matches_footer']
    assert len(final) == PARTITION_SIZE and final[:len(payload)] == payload
    assert footer['original_image_size'] == len(payload)
    with output.open('xb') as stream:
        stream.write(final)
    report = {
        'result': 'passed: file-only persistent recovery candidate verification',
        'image': str(output), 'sha256': digest(final), 'size': len(final),
        'base': str(SOURCE), 'base_sha256': digest(original),
        'boot_tested_reference': str(TESTED), 'boot_tested_reference_sha256': digest(tested),
        'boot_reference_evidence': 'evidence/rr-nofbe-runtime/identity.txt',
        'added_entries_from_base': {k: after[k] for k in sorted(set(after) - set(before))},
        'changed_existing_entries': [], 'removed_existing_entries': [],
        'all_existing_cpio_content_and_metadata_except_archive_inode_identical': True,
        'archive_inode_renumbering': {'retained_entries_vs_base': renumbered_from_base,
                                     'retained_entries_vs_diag2': renumbered_from_diag,
                                     'explanation': 'magiskboot assigns sequential inode IDs on serialization; no hardlink groups exist'},
        'exactly_tested_diag2_ramdisk_except_removed_entries': sorted(LOGGER),
        'no_bootdiag_logger_or_service': True,
        'busybox_matches_official_magisk_apk': True,
        'compressed_kernel_identical': True, 'compressed_kernel_sha256': digest(kernel),
        'decompressed_kernel_identical': True, 'kernel_dtb_identical': True,
        'recovery_dtbo_identical': True, 'header_changes': changes,
        'avb': footer, 'avbtool_verification': avb_result,
        'boot_payload_unchanged_by_footer_generation': True,
        'design': 'Exact tested early-init no-FBE script and rc retained; vendor fstab changed only through a RAM bind mount; diagnostic service and logger absent.',
        'limitations': [
            'This exact logger-free persistent image has not been booted or flashed by this agent.',
            'The same no-FBE assets booted RR8.7.3 Android10 through setup/home in diag2 according to parent and saved runtime evidence.',
            'Userdata remains unencrypted. Removing this workaround does not encrypt existing data or resolve the underlying keymaster incompatibility.',
            'The overlay accepts only the pinned stock vendor fstab hash; a vendor update requires revalidation.',
            'AVB footer uses algorithm NONE, as the existing unlocked custom-recovery setup; this is not an OEM-signed image.',
            'Existing Magisk recovery boot behavior and need for the appropriate recovery entry remain unchanged.',
        ],
        'device_operations': False, 'compiled_locally': False, 'this_image_boot_tested': False,
        'repack_script': str(Path(__file__).resolve()), 'log': str(work / 'repack.log'),
    }
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['result', 'image', 'sha256', 'size']}, indent=2))


if __name__ == '__main__':
    main()
