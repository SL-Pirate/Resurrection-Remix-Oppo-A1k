#!/usr/bin/env python3
"""Build a standard boot-v1 image from clean no-FBE recovery, without compiling."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repack_twrp_fix1 import ROOT, INPUTS, MAGISKBOOT, header, digest, cpio_entries

HERE = Path(__file__).resolve().parent
WORK = HERE / 'generation'
SOURCE = ROOT / 'staging/magisk-31.1-twrp-OP486C-nofbe-fix1.img'
STOCK_BOOT = ROOT / 'stock/partitions/boot.img'
STOCK_DTBO = ROOT / 'stock/partitions/dtbo.img'
OUTPUT = ROOT / 'staging/boot-magisk-31.1-OP486C-nofbe-fix1.img'
REPORT = ROOT / 'evidence/boot-magisk-nofbe-fix1-verification.json'
SIZE = 33554432


def avb_info(data, partition):
    magic, major, minor, original_size, offset, size = struct.unpack('!4s2L3Q28x', data[-64:])
    assert magic == b'AVBf'
    vb = data[offset:offset + size]
    h = struct.unpack('!4s2L2QL10QQL4x47sx80x', vb[:256])
    assert h[0] == b'AVB0'
    descriptors = vb[256 + h[3] + h[14]:256 + h[3] + h[14] + h[15]]
    at, matched = 0, []
    while at < len(descriptors):
        tag, following = struct.unpack_from('!2Q', descriptors, at)
        desc = descriptors[at:at + 16 + following]
        if tag == 2:
            fields = struct.unpack('!3Q32s4L60s', desc[:132])
            _, _, image_size, algorithm, plen, slen, dlen, flags, _ = fields
            name = desc[132:132 + plen].decode()
            if name == partition:
                assert algorithm.rstrip(b'\0') == b'sha256'
                salt = desc[132 + plen:132 + plen + slen]
                expected = desc[132 + plen + slen:132 + plen + slen + dlen]
                actual = hashlib.sha256(salt + data[:image_size]).digest()
                matched.append({'partition': name, 'algorithm_type': h[5],
                                'footer_version': f'{major}.{minor}',
                                'original_image_size': original_size,
                                'descriptor_image_size': image_size,
                                'vbmeta_offset': offset, 'vbmeta_size': size,
                                'salt': salt.hex(), 'flags': flags,
                                'expected_digest': expected.hex(), 'computed_digest': actual.hex(),
                                'hash_matches': expected == actual,
                                'image_size_matches_footer': original_size == image_size})
        at += 16 + following
    assert len(matched) == 1 and at == len(descriptors)
    return matched[0]


def android_image_id(data):
    h, checksum = header(data), hashlib.sha1()
    page = h['page_size']; offset = page
    for name in ['kernel', 'ramdisk', 'second']:
        size = h[name + '_size']
        checksum.update(data[offset:offset + size]); checksum.update(struct.pack('<I', size))
        offset += (size + page - 1) // page * page
    size, offset = h['recovery_dtbo_size'], h['recovery_dtbo_offset']
    checksum.update(data[offset:offset + size]); checksum.update(struct.pack('<I', size))
    return checksum.digest() + bytes(12)


def main():
    assert not any(p.exists() for p in [WORK, OUTPUT, REPORT])
    original, stock_boot, stock_dtbo = SOURCE.read_bytes(), STOCK_BOOT.read_bytes(), STOCK_DTBO.read_bytes()
    assert digest(original) == 'e31d832fb3155c5c7c48551c3cc8abf8487c22a94d8da20dd5f7170d9684f0f1'
    assert digest(stock_boot) == '939728e14db06a428f34fa49cd6037d36635974091e5368f6f3139cef774a7c5'
    assert digest(stock_dtbo) == 'b8b53f32a583052b64c446cf34359531953e14505ecdef01acb7032443ea0ef2'
    old = header(original)
    assert old['header_version'] == 1 and old['second_size'] == 0
    assert original[576:608] == android_image_id(original)
    off, size = old['recovery_dtbo_offset'], old['recovery_dtbo_size']
    embedded = original[off:off + size]
    assert embedded == stock_dtbo[:size]
    assert digest(embedded) == '146a9aa3561bdb21d6574950d97ca37b64b2c1f3109f07bdb64379378fe04d49'
    stock_footer = avb_info(stock_boot, 'boot')
    assert stock_footer['hash_matches']
    assert stock_footer['salt'] == '246b7edc65ee1ae126e4c0a00b8a44763159a1cc86ed7dc5badbbda2a2c8aa30'
    WORK.mkdir()
    # magiskboot clones original DTBO fields even if the component is absent.
    # Normalize a separate, correctly truncated standard-v1 template first.
    template = bytearray(original[:off])
    struct.pack_into('<IQ', template, 1632, 0, 0)
    template[576:608] = android_image_id(template)
    (WORK / 'standard-template.img').write_bytes(template)
    logs = []

    def run(cmd, cwd=WORK):
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
        logs.append(repr(cmd) + '\n' + result.stdout + result.stderr)
        (WORK / 'generation.log').write_text('\n'.join(logs))
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout + result.stderr

    def avb(*argv):
        return run(['podman', 'run', '--rm', '--network=none', '--security-opt', 'label=disable',
                    '-v', str(WORK) + ':/work:rw', '-v', str(INPUTS / 'avbtool-v1.1.0.py') + ':/avbtool:ro',
                    'localhost/oppo-a1k-twrp9:local', 'python2', '/avbtool', *argv])

    # Already-compressed components are retained byte-for-byte by -n.
    run([str(MAGISKBOOT), 'unpack', '-n', 'standard-template.img'])
    assert not (WORK / 'recovery_dtbo').exists()
    run([str(MAGISKBOOT), 'repack', '-n', 'standard-template.img', 'boot.img'])
    payload = (WORK / 'boot.img').read_bytes()
    assert payload == template
    avb('add_hash_footer', '--image', '/work/boot.img', '--partition_name', 'boot',
        '--partition_size', str(SIZE), '--algorithm', 'NONE', '--salt', stock_footer['salt'])
    avb_verified = avb('verify_image', '--image', '/work/boot.img')
    avb_description = avb('info_image', '--image', '/work/boot.img')
    final = (WORK / 'boot.img').read_bytes()
    new, footer = header(final), avb_info(final, 'boot')
    assert new['recovery_dtbo_size'] == new['recovery_dtbo_offset'] == 0
    assert footer['hash_matches'] and footer['image_size_matches_footer'] and footer['algorithm_type'] == 0
    assert len(final) == SIZE and footer['original_image_size'] == len(payload) == off
    assert final[:len(payload)] == template
    assert final[old['page_size']:off] == original[old['page_size']:off]
    assert final[576:608] == android_image_id(final)
    # AVB alignment padding is zero: the removed recovery table is not hidden
    # between the new boot payload and its boot-specific vbmeta descriptor.
    assert not any(final[off:footer['vbmeta_offset']])
    for name, source in [('original', SOURCE), ('candidate', WORK / 'boot.img')]:
        dest = WORK / name; dest.mkdir()
        run([str(MAGISKBOOT), 'unpack', str(source)], dest)
    hashes = {}
    for name in ['kernel', 'kernel_dtb', 'ramdisk.cpio']:
        a, b = (WORK / 'original' / name).read_bytes(), (WORK / 'candidate' / name).read_bytes()
        assert a == b, name
        hashes[name] = digest(a)
    assert not (WORK / 'candidate/recovery_dtbo').exists()
    assert cpio_entries(WORK / 'original/ramdisk.cpio') == cpio_entries(WORK / 'candidate/ramdisk.cpio')
    with OUTPUT.open('xb') as out:
        out.write(final)
    (HERE / 'candidate-header.bin').write_bytes(final[:4096])
    report = {
        'result': 'passed: standard boot image generation and component/AVB checks; remote LK validation pending',
        'image': str(OUTPUT), 'size': len(final), 'sha256': digest(final),
        'source': str(SOURCE), 'source_sha256': digest(original),
        'standard_boot_v1': True, 'recovery_dtbo_size': 0, 'recovery_dtbo_offset': 0,
        'embedded_recovery_dtbo_physically_removed': True,
        'partition_dtbo_fallback_identical': True,
        'removed_table_size': size, 'removed_table_sha256': digest(embedded),
        'stock_dtbo_partition_sha256': digest(stock_dtbo),
        'compressed_kernel_and_ramdisk_bytes_identical': True,
        'all_ramdisk_cpio_bytes_and_entries_identical': True,
        'decompressed_component_sha256': hashes,
        'header_changes': {k: {'source': old[k], 'boot': new[k]} for k in old if old[k] != new[k]},
        'header_image_id_recomputed_and_verified': True,
        'magiskboot_repack_exactly_matches_standard_template': True,
        'avb': footer, 'avbtool_verification': avb_verified, 'avbtool_info': avb_description,
        'avb_salt_source': {'image': str(STOCK_BOOT), 'sha256': digest(stock_boot), 'descriptor': stock_footer},
        'limitations': [
            'This exact boot image has not been flashed or booted by this agent.',
            'Normal-mode RR, root and sensors succeeded with the earlier RAM test; that does not certify every peripheral or this storage boot path.',
            'Requires the intended LK normal-storage boot profile and unchanged valid stock dtbo partition.',
            'Magisk RECOVERYMODE=true remains intentional for legacy SAR; holding volume-up can select the bundled TWRP ramdisk.',
            'Userdata remains unencrypted through the tested RAM fstab override.',
            'AVB algorithm NONE provides an integrity hash, not an OEM signature; unlocked boot configuration is required.',
        ],
        'device_operations': False, 'compiled_locally': False,
        'script': str(Path(__file__).resolve()), 'log': str(WORK / 'generation.log'),
    }
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['result', 'image', 'sha256', 'size']}, indent=2))


if __name__ == '__main__':
    main()
