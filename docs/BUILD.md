# Build and reproduce

## LK

Base and port revisions are recorded in `manifests/lk-provenance.json`. `patches/lk/0001-op486c-tested-port.patch` consolidates the final port against the pinned base; **do not also apply the old numbered incremental patches**. Historical experiments that were not in the final source are excluded.

Obtain the base, then run the preparation script against a clean checkout:

```sh
git clone https://github.com/svoboda18/lk build/lk
git -C build/lk checkout 37ec8bcbc4361c0e267617f517d154656804c17a
python3 scripts/prepare_lk.py build/lk
podman build -f tools/Containerfile.twrp9 -t oppo-a1k-twrp9:local .
podman run --rm -v "$PWD/build/lk:/work:Z" -w /work   oppo-a1k-twrp9:local make -j8 oppo6762_18540 NO_SIGN=yes OPPO_RESCUE_FASTBOOT=yes
```

Run compilation on your designated build machine. The original build used eight workers. The public preparation script restores the recorded toolchain symlinks and verifies each patched file. The base toolchain binaries are upstream inputs, not stored in this repository. The unsigned build does not need private signing keys. This configuration uses the early DTB loader rather than a committed stock built-in DTB.

The build's `lk.bin`/image names can be misleading: `lk-no-mtk-header.bin` is the raw payload; the generated `lk.img` has the MediaTek wrapper. The tested flash image is the wrapped image padded to exactly **1,048,576 bytes**. Verify wrapper/entrypoint and partition capacity before packaging. Builds include timestamps, so a fresh binary need not match the historical hash byte-for-byte.

Available actual-source tests take the patched source directory:

```sh
python3 tools/lk-panel-review/test-rescue-storage-menu.py build/lk
python3 tools/ril-review/lk-modem-export/test-modem-export.py build/lk
```

## TWRP

Use the Android 9 TeamWin/Omni source revisions in `manifests/twrp-build-manifest.xml`, and copy `device/oppo/OP486C` into that source tree. Supply `prebuilt/kernel` and `prebuilt/recovery_dtbo` extracted from **your matching stock recovery**. The latter is the embedded recovery DTBO, not the whole DTBO partition. The tree does not include those firmware binaries.

The original build used the included Ubuntu 20.04 container, `lunch omni_OP486C-eng`, and `mka -j8 recoveryimage`. Apply `patches/twrp/MtpDevHandle-close-before-open.patch` to the source root for the final MTP fix; the historical bring-up built this library separately and repacked it with `tools/twrp-fix1/recovery.fstab` into the initial recovery. `tools/repack_twrp_fix1.py` records that finalization and independent hash checks.

## Magisk and BOOT packaging

These are research workflow scripts, not a complete fresh-build orchestrator. They expect upstream `magiskboot`, avbtool v1.1.0 (Python 2), stock images and intermediate recovery/Magisk images at the paths named in each script. The included container supplies Python 2. No prebuilt tools, original images or keys are in Git.

Historical sequence: TWRP bringup1 → fix1 recovery repack → file-only Magisk patch and AVB validation → diagnostic no-FBE test → logger-free combined recovery (`tools/recovery-nofbe/repack.py`) → standard BOOT conversion (`tools/boot-nofbe-fix1/generate.py`). The verifier refuses unexpected inputs. Diagnostic scripts are retained to explain provenance, not presented as release flash instructions.

The final conversion removes the embedded recovery DTBO, sets its size and offset to zero, preserves the tested kernel/ramdisk and `RECOVERYMODE=true`, recalculates the image ID, and regenerates a BOOT AVB footer with algorithm NONE. See the technical and maintenance notes before updating Magisk.

## Telephony repair

Use the **original** TeleService.apk whose SHA-256 is pinned in `manifests/telephony.json`. With Apktool 2.11.1:

```sh
java -jar apktool_2.11.1.jar d -r TeleService.apk -o decoded
(cd decoded && patch -p1 < /absolute/path/to/patches/telephony/PhoneUtils-nonnumeric-modem-id.patch)
java -jar apktool_2.11.1.jar b -j 8 decoded -o TeleService-unsigned.apk
zipalign -f 4 TeleService-unsigned.apk TeleService-aligned.apk
apksigner sign --key "$PLATFORM_KEY" --cert "$PLATFORM_CERT"   --out TeleService.apk TeleService-aligned.apk
apksigner verify --print-certs TeleService.apk
```

Signing inputs must match the original certificate; the tested APK uses the public AOSP development platform certificate. Obtain those inputs separately. The private-key-shaped public test fixture is deliberately not committed here. Compare signer SHA-256 and ensure only `classes.dex` changes among APK payload members. Put the result in `modules/telephony/system/priv-app/TeleService/TeleService.apk` before packaging an overlay. A normal `adb install -r` is rejected for this persistent app.

## Optional btop and swap

The btop wrapper uses the official ARM64 Termux btop 1.4.8 binary plus libc++ 30; source package hashes are in `manifests/termux-packages.json`. Extract the executable into `modules/btop/bin/btop` and the C++ runtime into `modules/btop/lib/libc++_shared.so`. No Termux app or local compilation was required on the tested phone. Hashes were compared to the downloaded package indexes; repository PGP signatures were not independently verified.

The swap service initializes zRAM only if it is uninitialized. It enables the 4 GiB swapfile only if already present. The original file was fully allocated with `dd`, mode 0600, then initialized with `mkswap`; no partition resizing was used. Do not use a sparse file or reformat an active swap area. See the maintenance notes for removal.
