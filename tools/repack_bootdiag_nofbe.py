#!/usr/bin/env python3
"""Repack the tested diagnostic recovery with a temporary no-FBE fstab overlay."""
import json
from pathlib import Path
import shutil
import subprocess
from repack_twrp_fix1 import ROOT, MAGISKBOOT, INPUTS, PARTITION_SIZE, header, cpio_entries, digest
from verify_finalize_twrp_magisk_fix1 import avb_hash

SOURCE = ROOT / 'staging/magisk-31.1-twrp-OP486C-fix1-diag1-UNTESTED.img'
ASSETS = ROOT / 'tools/bootdiag-nofbe'
WORK = ASSETS / 'repack'
OUTPUT = ROOT / 'staging/magisk-31.1-twrp-OP486C-diag2-nofbe.img'
REPORT = ROOT / 'evidence/twrp-magisk-diag2-nofbe-verification.json'


def main():
    assert not WORK.exists() and not OUTPUT.exists() and not REPORT.exists()
    original = SOURCE.read_bytes()
    assert digest(original) == 'a9213ed47c64cd369fea3a407e79c43cce789b8d1d3e679ff808635704656766'
    WORK.mkdir()
    logs = []
    def run(cmd, cwd=WORK):
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        logs.append(repr(cmd) + '\n' + result.stdout + result.stderr)
        (WORK / 'repack.log').write_text('\n'.join(logs))
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout + result.stderr
    def avb(*args):
        return run(['podman','run','--rm','--network=none','--security-opt','label=disable',
                    '-v',str(WORK)+':/work:rw','-v',str(INPUTS/'avbtool-v1.1.0.py')+':/avbtool:ro',
                    'localhost/oppo-a1k-twrp9:local','python2','/avbtool',*args])
    shutil.copyfile(SOURCE, WORK / 'base.img')
    avb('erase_footer','--image','/work/base.img')
    run([str(MAGISKBOOT),'unpack','base.img'])
    before = cpio_entries(WORK / 'ramdisk.cpio')
    files = {'overlay.d/op486c-no-fbe.rc':('0644','op486c-no-fbe.rc'),
             'overlay.d/sbin/op486c-bootdiag/no-fbe.sh':('0750','no-fbe.sh'),
             'overlay.d/sbin/op486c-bootdiag/fstab.no-fbe':('0644','fstab.no-fbe')}
    additions = []
    for target, (mode, source) in files.items():
        assert target not in before
        shutil.copyfile(ASSETS / source, WORK / source)
        additions.append(f'add {mode} {target} {source}')
    run([str(MAGISKBOOT),'cpio','ramdisk.cpio',*additions])
    (WORK / 'kernel').rename(WORK / 'kernel-original')
    run([str(MAGISKBOOT),'repack','base.img','recovery.img'])
    avb('add_hash_footer','--image','/work/recovery.img','--partition_name','recovery',
        '--partition_size',str(PARTITION_SIZE),'--algorithm','NONE','--salt',avb_hash(original)['salt'])
    avb_result = avb('verify_image','--image','/work/recovery.img')
    verify = WORK / 'verify'; verify.mkdir()
    run([str(MAGISKBOOT),'unpack',str(WORK/'recovery.img')], verify)
    after = cpio_entries(verify / 'ramdisk.cpio')
    assert set(after) - set(before) == set(files)
    assert all(after[name] == value for name, value in before.items())
    for target, (mode, source) in files.items():
        assert after[target]['sha256'] == digest((ASSETS / source).read_bytes())
        assert after[target]['mode'] == 0o100000 + int(mode, 8)
    final = (WORK / 'recovery.img').read_bytes()
    old, new = header(original), header(final)
    changes = {k:{'base':old[k],'diagnostic':new[k]} for k in old if old[k] != new[k]}
    assert set(changes) <= {'ramdisk_size','recovery_dtbo_offset','image_id'}
    assert original[old['page_size']:old['page_size']+old['kernel_size']] == final[new['page_size']:new['page_size']+new['kernel_size']]
    for name in ['kernel_dtb','recovery_dtbo']:
        assert (WORK/name).read_bytes() == (verify/name).read_bytes()
    assert (WORK/'kernel-original').read_bytes() == (verify/'kernel').read_bytes()
    footer = avb_hash(final)
    assert footer['hash_matches'] and footer['image_size_matches_footer'] and len(final) == PARTITION_SIZE
    with OUTPUT.open('xb') as output:
        output.write(final)
    report = {'result':'passed: offline diagnostic repack static checks only','image':str(OUTPUT),
              'sha256':digest(final),'size':len(final),'source':str(SOURCE),'source_sha256':digest(original),
              'added_entries':{k:after[k] for k in sorted(set(after)-set(before))},
              'all_existing_ramdisk_entries_identical':True,'compressed_kernel_identical':True,
              'decompressed_kernel_identical':True,'kernel_dtb_identical':True,'recovery_dtbo_identical':True,
              'header_changes':changes,'avb':footer,'avbtool_verification':avb_result,
              'design':{'trigger':'synchronous early-init Magisk exec',
                        'target':'/vendor/etc/fstab.mt6765',
                        'override':'RAM-only file bind mount; remove only userdata fileencryption=aes-256-xts',
                        'existing_logger_preserved':True,
                        'script_policy':'pinned source/destination hashes; matching SELinux label; no format'},
              'limitations':['Runtime boot not yet tested; this test leaves userdata unencrypted.',
                             'Does not establish the underlying keymaster root cause.'],
              'device_operations':False,'compiled_locally':False,'boot_tested':False,
              'script':str(Path(__file__).resolve()),'log':str(WORK/'repack.log')}
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['result','image','sha256','size']},indent=2))


if __name__ == '__main__':
    main()
