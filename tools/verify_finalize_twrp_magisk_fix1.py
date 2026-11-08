#!/usr/bin/env python3
"""Independently validate the file-only Magisk patch and finalize AVB."""
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile
from repack_twrp_fix1 import ROOT, MAGISKBOOT, INPUTS, PARTITION_SIZE, header, cpio_entries, digest

BASE = ROOT / 'staging/twrp-3.7.0_9-OP486C-bringup1-fix1.img'
RAW = ROOT / 'staging/magisk-31.1-twrp-fix1-unfinalized.img'
FINAL = ROOT / 'staging/magisk-31.1-twrp-OP486C-fix1-experimental.img'
REPORT = ROOT / 'evidence/twrp-magisk-fix1-verification.json'
WORK = ROOT / 'tools/twrp-magisk-fix1-verification-final'


def contents(path):
    data = path.read_bytes()
    result, offset = {}, 0
    while True:
        assert data[offset:offset + 6] == b'070701'
        values = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        name = data[offset + 110:offset + 109 + values[11]].decode()
        offset = (offset + 110 + values[11] + 3) & ~3
        content = data[offset:offset + values[6]]
        offset = (offset + values[6] + 3) & ~3
        if name == 'TRAILER!!!':
            return result
        result[name] = content


def avb_hash(data):
    magic, major, minor, orig_size, vb_offset, vb_size = struct.unpack('!4s2L3Q28x', data[-64:])
    assert magic == b'AVBf'
    vb = data[vb_offset:vb_offset + vb_size]
    fields = struct.unpack('!4s2L2QL10QQL4x47sx80x', vb[:256])
    assert fields[0] == b'AVB0' and fields[5] == 0 and fields[3] == 0
    desc = vb[256 + fields[3] + fields[14]:256 + fields[3] + fields[14] + fields[15]]
    tag, nbf, image_size, algorithm, part_len, salt_len, digest_len, flags, _ = struct.unpack('!3Q32s4L60s', desc[:132])
    assert tag == 2 and len(desc) == nbf + 16 and algorithm.rstrip(b'\0') == b'sha256'
    part = desc[132:132 + part_len].decode()
    salt = desc[132 + part_len:132 + part_len + salt_len]
    expected = desc[132 + part_len + salt_len:132 + part_len + salt_len + digest_len]
    actual = hashlib.sha256(salt + data[:image_size]).digest()
    assert part == 'recovery'
    return dict(footer_version=f'{major}.{minor}', original_image_size=orig_size,
                vbmeta_offset=vb_offset, vbmeta_size=vb_size, algorithm='NONE',
                partition=part, descriptor_image_size=image_size,
                image_size_matches_footer=orig_size == image_size,
                hash_algorithm='sha256', salt=salt.hex(),
                expected_digest=expected.hex(), computed_digest=actual.hex(),
                hash_matches=actual == expected, flags=flags)


def main():
    assert not FINAL.exists() and not REPORT.exists() and not WORK.exists()
    base, raw = BASE.read_bytes(), RAW.read_bytes()
    assert digest(base) == '513d3db089d6e37146051b624a9ba107aa13e228f99c7a17372d3106ff6e7e37'
    assert digest(raw) == 'bf275dc3b80b05ef044d5d1d598fc6a12e5f9a3395bdda4ad459d8cb09ebafdf'
    assert len(base) == len(raw) == PARTITION_SIZE
    WORK.mkdir()
    logs = []

    def run(command, cwd=WORK):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
        logs.append('COMMAND ' + repr(command) + '\n' + result.stdout + result.stderr)
        (WORK / 'verification.log').write_text('\n'.join(logs))
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout + result.stderr

    def avb(*args):
        return run(['podman', 'run', '--rm', '--network=none', '--security-opt', 'label=disable',
                    '-v', str(WORK) + ':/work:rw', '-v', str(INPUTS / 'avbtool-v1.1.0.py') + ':/avbtool:ro',
                    'localhost/oppo-a1k-twrp9:local', 'python2', '/avbtool', *args])

    for folder, source in [('standalone', BASE), ('combined', RAW)]:
        (WORK / folder).mkdir()
        run([str(MAGISKBOOT), 'unpack', str(source)], WORK / folder)
    bdir, cdir = WORK / 'standalone', WORK / 'combined'
    bm, cm = cpio_entries(bdir / 'ramdisk.cpio'), cpio_entries(cdir / 'ramdisk.cpio')
    bc, cc = contents(bdir / 'ramdisk.cpio'), contents(cdir / 'ramdisk.cpio')
    added = sorted(set(cm) - set(bm)); removed = sorted(set(bm) - set(cm))
    expected_added = ['.backup', '.backup/.magisk', '.backup/.rmlist', '.backup/init.xz',
                      'overlay.d', 'overlay.d/sbin', 'overlay.d/sbin/init-ld.xz', 'overlay.d/sbin/magisk.xz']
    changed = [name for name in bm if bm[name] != cm.get(name)]
    assert added == expected_added and not removed and changed == ['init']
    for field in ['mode', 'uid', 'gid', 'rdevmajor', 'rdevminor']:
        assert bm['init'][field] == cm['init'][field]
    assert lzma.decompress(cc['.backup/init.xz']) == bc['init']
    apk = ROOT / 'downloads/Magisk-v31.1.apk'
    assert digest(apk.read_bytes()) == '89cefac0a318afa39fb3880c45c87b036c05bc1ebf02a7a715b7f8d7c26ac6e7'
    with zipfile.ZipFile(apk) as z:
        payloads = {'init': ('libmagiskinit.so', cc['init']),
                    'overlay.d/sbin/magisk.xz': ('libmagisk.so', lzma.decompress(cc['overlay.d/sbin/magisk.xz'])),
                    'overlay.d/sbin/init-ld.xz': ('libinit-ld.so', lzma.decompress(cc['overlay.d/sbin/init-ld.xz']))}
        for path, (member, actual) in payloads.items():
            assert actual == z.read('lib/arm64-v8a/' + member), path
    flags = dict(line.split('=', 1) for line in cc['.backup/.magisk'].decode().splitlines())
    expected_flags = {'KEEPVERITY':'true', 'KEEPFORCEENCRYPT':'true', 'RECOVERYMODE':'true',
                      'VENDORBOOT':'false', 'PREINITDEVICE':'userdata', 'SHA1':hashlib.sha1(base).hexdigest()}
    assert flags == expected_flags
    bk, ck = (bdir / 'kernel').read_bytes(), (cdir / 'kernel').read_bytes()
    needle, replacement = b'skip_initramfs\0', b'want_initramfs\0'
    assert bk.count(needle) == 1 and bk.replace(needle, replacement) == ck
    dt_hashes = {}
    for name in ['kernel_dtb', 'recovery_dtbo']:
        assert (bdir / name).read_bytes() == (cdir / name).read_bytes()
        dt_hashes[name] = digest((cdir / name).read_bytes())
    bh, ch = header(base), header(raw)
    changes = {name:{'standalone':bh[name], 'combined':ch[name]} for name in bh if bh[name] != ch[name]}
    assert set(changes) <= {'kernel_size', 'ramdisk_size', 'image_id', 'recovery_dtbo_offset'}
    before_avb = avb_hash(raw)
    shutil.copyfile(RAW, WORK / 'recovery.img')
    if not before_avb['hash_matches']:
        avb('erase_footer', '--image', '/work/recovery.img')
        assert (WORK / 'recovery.img').read_bytes() == raw[:before_avb['original_image_size']]
        avb('add_hash_footer', '--image', '/work/recovery.img', '--partition_name', 'recovery',
            '--partition_size', str(PARTITION_SIZE), '--algorithm', 'NONE', '--salt', before_avb['salt'])
    verified = avb('verify_image', '--image', '/work/recovery.img')
    final = (WORK / 'recovery.img').read_bytes()
    after_avb = avb_hash(final)
    assert after_avb['hash_matches'] and after_avb['image_size_matches_footer'] and len(final) == PARTITION_SIZE
    assert final[:before_avb['original_image_size']] == raw[:before_avb['original_image_size']]
    assert header(final) == ch
    with FINAL.open('xb') as output:
        output.write(final)
    report = {
        'result':'passed: independent combined fix1 static verification and AVB finalization',
        'final_image':str(FINAL), 'size':len(final), 'sha256':digest(final),
        'unfinalized_image':str(RAW), 'unfinalized_sha256':digest(raw),
        'standalone_image':str(BASE), 'standalone_sha256':digest(base),
        'header_changes':changes, 'all_other_header_fields_unchanged':True,
        'device_tree_hashes':dt_hashes, 'device_trees_identical':True,
        'kernel':{'decompressed_size':len(ck), 'sha256':digest(ck),
                  'only_change':'skip_initramfs -> want_initramfs', 'replacement_count':1,
                  'replacement_offset':bk.index(needle), 'exact_expected_replacement':True},
        'ramdisk':{'standalone_entries':len(bm), 'combined_entries':len(cm), 'added_paths':added,
                   'removed_paths':removed, 'changed_existing_paths':changed,
                   'original_init_backup_exact':True, 'official_apk_payloads_exact':True,
                   'flags':flags, 'all_other_existing_entries_preserved':True,
                   'fix1_fstab_sha256':cm['etc/recovery.fstab']['sha256'],
                   'fix1_mtp_library_sha256':cm['sbin/libtwrpmtp-ffs.so']['sha256'],
                   'comparison_scope':'Content, paths, modes, ownership and device numbers; archive inode ordering/timestamps excluded.'},
        'avb':{'before':before_avb, 'after':after_avb, 'regenerated':not before_avb['hash_matches'],
               'original_boot_payload_bytes_preserved':True, 'avbtool_verification':verified},
        'script':str(Path(__file__).resolve()), 'log':str(WORK / 'verification.log'),
        'device_operations':False, 'compiled_locally':False, 'boot_tested':False,
        'limitations':['Static validation does not establish RR root or recovery runtime compatibility.',
                       'Unsigned AVB hash correctness does not establish OEM signature acceptance.']}
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key:report[key] for key in ['result', 'final_image', 'size', 'sha256']}, indent=2))


if __name__ == '__main__':
    main()
