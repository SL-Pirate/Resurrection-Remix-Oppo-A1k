#!/system/bin/sh
# File-only Magisk v31.1 patch preparation for this OPPO A1k recovery.
# Run on the SAME phone as Android shell UID 2000, using the extracted BusyBox:
# ASH_STANDALONE=1 /data/local/tmp/magisk-patch-assets/busybox sh \
#   /data/local/tmp/patch-stock-recovery.sh \
#   /data/local/tmp/magisk-patch-assets \
#   /sdcard/Download/OP486C-stock-recovery.img \
#   /data/local/tmp/oppo-a1k-magisk-result
# Optional fourth argument: stock (default) or twrp-bringup1. The latter
# accepts only the pinned standalone bring-up image and creates an EXPERIMENTAL
# combined candidate requiring separate rooted-Android and TWRP boot tests.
# All output is confined to a NEW directory under /data/local/tmp.
# Input and APK assets are hash-pinned. This script never installs its output.

patch_die() { printf '%s\n' "ERROR: $*" >&2; exit 1; }
patch_hash() { sha256sum "$1" | cut -d ' ' -f 1; }

[ "$#" -eq 3 ] || [ "$#" -eq 4 ] || patch_die "Usage: $0 ASSET_DIRECTORY RECOVERY_FILE NEW_OUTPUT_DIRECTORY [stock|twrp-bringup1]"
patch_profile=${4:-stock}
case "$patch_profile" in
    stock)
        patch_input_sha=a45744b4bf0095939ff4209e6b0f5ed3095e19ffc8a26ddf72fb205fa77355db
        patch_output_name=magisk-31.1-stock-recovery.img
        ;;
    twrp-bringup1)
        patch_input_sha=a35e5ef1b7e9518068446fe3d771de0e2787b1e8bcbf01b57db89767dc0fcdba
        patch_output_name=magisk-31.1-twrp-3.7.0_9-OP486C-bringup1-experimental.img
        ;;
    *) patch_die "Unknown profile: $patch_profile" ;;
esac
(set -o standalone) 2>/dev/null || patch_die "Use the APK's BusyBox ash as shown in this script's header"
set -o standalone
[ "$(id -u)" = 2000 ] || patch_die "Run as the ordinary Android ADB shell (UID 2000), without su"
[ -x /system/bin/getprop ] || patch_die "Requires booted Android on the target phone"
[ "$(getprop ro.product.device)" = OP486C ] || patch_die "Wrong device"
[ "$(getprop ro.product.model)" = CPH1923 ] || patch_die "Wrong model"
[ "$(getprop ro.build.version.sdk)" = 28 ] || patch_die "Requires the recorded stock Android 9 environment"
[ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || patch_die "Wrong ABI"
[ "$(getprop ro.build.fingerprint)" = 'OPPO/CPH1923/OP486C:9/PPR1.180610.011/2021030000:user/release-keys' ] || patch_die "Stock build identity changed"

patch_assets=$(readlink -f "$1") || patch_die "Cannot resolve assets"
patch_input=$(readlink -f "$2") || patch_die "Cannot resolve input"
patch_parent=$(readlink -f "${3%/*}") || patch_die "Cannot resolve output parent"
patch_name=${3##*/}
case "$patch_assets" in /data/local/tmp/*) ;; *) patch_die "Assets must be under /data/local/tmp" ;; esac
case "$patch_assets" in *[!a-zA-Z0-9_./-]*) patch_die "Use a simple assets path without spaces" ;; esac
case "$patch_name" in ''|.|..|*[!a-zA-Z0-9_-]*) patch_die "Use a simple, new output directory name" ;; esac
case "$patch_parent" in /data/local/tmp|/data/local/tmp/*) ;; *) patch_die "Output must be under /data/local/tmp" ;; esac
[ -d "$patch_parent" ] || patch_die "Output parent does not exist"
patch_output_dir=$patch_parent/$patch_name
[ ! -e "$patch_output_dir" ] && [ ! -L "$patch_output_dir" ] || patch_die "Output already exists; choose a new directory"
case "$patch_input" in /dev/*|/proc/*|/sys/*) patch_die "Input must be a regular image file, never a device node" ;; esac
[ -f "$patch_input" ] && [ ! -b "$patch_input" ] && [ ! -c "$patch_input" ] || patch_die "Input is not a regular file"
[ "$(stat -c %s "$patch_input")" = 33554432 ] || patch_die "Recovery input must be exactly 32 MiB"
[ "$(patch_hash "$patch_input")" = "$patch_input_sha" ] || patch_die "Input differs from the pinned $patch_profile recovery image"

# Check each executable/script against its member bytes in the saved official APK.
for patch_asset in app_functions.sh util_functions.sh boot_patch.sh busybox magisk magiskinit magiskboot init-ld; do
    [ -f "$patch_assets/$patch_asset" ] && [ ! -L "$patch_assets/$patch_asset" ] || patch_die "Missing regular asset: $patch_asset"
done
(
    cd "$patch_assets" || exit 1
    sha256sum -c <<'MAGISK_ASSET_HASHES'
d257b950f2ad33cf887487de75de80d1b2c67a89ff4f0347586e5cd0e2d2ab1e  app_functions.sh
417866965cb3845c7ea085f1499393efcf65e6c7cf1321e7911a3bd7c25a6c8d  util_functions.sh
721e879b9ebdda200796d95dbe6f8e9776cfff89b7550fdb5ca77ac87dcede17  boot_patch.sh
4d60ab3f5a59ebb2ca863f2f514e6924401b581e9b64f602665c008177626651  busybox
fb0ba1b1f3472d34b8ae21edd3a69c2a44f46a3a7c34e85e37c6b2b57d22b9ec  magisk
c0c7cc1c8e1afb92bff602164f6aa1bb4103f5028d076216d8bef48496e2f4dc  magiskinit
97e9ec75731103d31c9e1effca7a50c6444309ce8f78c2ec27e9fe721da4bb54  magiskboot
edc355f90c76bed3ae4b93fd098cd15f5e688840ea5aa104d65ac9dd210ae1d7  init-ld
MAGISK_ASSET_HASHES
) || patch_die "Asset hashes differ from Magisk v31.1 APK"

umask 077
mkdir -m 700 "$patch_output_dir" || patch_die "Cannot create new output directory"
patch_work_dir=$patch_output_dir/work
mkdir -m 700 "$patch_work_dir" "$patch_output_dir/verify" || patch_die "Cannot create work directories"
for patch_asset in app_functions.sh util_functions.sh boot_patch.sh busybox magisk magiskinit magiskboot init-ld; do
    cp "$patch_assets/$patch_asset" "$patch_work_dir/$patch_asset" || patch_die "Cannot copy asset"
done
cp "$patch_input" "$patch_work_dir/input-recovery.img" || patch_die "Cannot copy input image"
[ "$(patch_hash "$patch_work_dir/input-recovery.img")" = "$patch_input_sha" ] || patch_die "Input copy hash mismatch"
cd "$patch_work_dir" || patch_die "Cannot enter patch directory"
chmod 755 busybox magisk magiskinit magiskboot init-ld || patch_die "Cannot set executable permissions"

# Sourcing util_functions defines helpers; app_functions overrides mount_partitions
# and get_flags with the app's READ-ONLY non-root versions. Do not call the root
# utility version of mount_partitions, setup_flashable, check_data, or app_init.
unset KEEPVERITY KEEPFORCEENCRYPT PATCHVBMETAFLAG RECOVERYMODE LEGACYSAR
unset SYSTEM_AS_ROOT ISENCRYPTED VENDORBOOT SLOT PREINITDEVICE BOOTNAND
unset MAGISKTMP MAKEDEV SOURCEDMODE MODPATH
export BOOTMODE=true
. ./util_functions.sh
. ./app_functions.sh
# Preserve diagnostic files on failure; bypass upstream abort's cleanup paths.
abort() { patch_die "$*"; }
[ "$MAGISK_VER" = 31.1 ] && [ "$MAGISK_VER_CODE" = 31100 ] || patch_die "Wrong Magisk script version"
mount_partitions
RECOVERYMODE=true
get_flags
# The OPPO recovery boot path omits ro.boot.vbmeta.* even while the separate
# partition is present. Corroborate it using the exact observed GPT geometry.
if [ "$PATCHVBMETAFLAG" = true ] &&
   grep -qx 'PARTNAME=vbmeta' /sys/class/block/mmcblk0p10/uevent &&
   [ "$(cat /sys/class/block/mmcblk0p10/start)" = 392256 ] &&
   [ "$(cat /sys/class/block/mmcblk0p10/size)" = 16384 ]; then
    printf '%s\n' 'Separate vbmeta confirmed through sysfs; preserving image vbmeta flags.'
    PATCHVBMETAFLAG=false
fi
[ "$SYSTEM_AS_ROOT" = true ] && [ "$LEGACYSAR" = true ] && [ -z "$SLOT" ] || patch_die "Unexpected SAR/slot environment"
[ "$KEEPVERITY" = true ] && [ "$KEEPFORCEENCRYPT" = true ] || patch_die "Unexpected verity/encryption defaults"
[ "$PATCHVBMETAFLAG" = false ] || patch_die "Expected separate vbmeta was not detected"
[ "$RECOVERYMODE" = true ] && [ "$VENDORBOOT" = false ] || patch_die "Wrong recovery mode"

{
    printf 'PROFILE=%s\n' "$patch_profile"
    printf 'MAGISK_VER=%s\nMAGISK_VER_CODE=%s\n' "$MAGISK_VER" "$MAGISK_VER_CODE"
    printf 'BOOTMODE=%s\nSYSTEM_AS_ROOT=%s\nLEGACYSAR=%s\n' "$BOOTMODE" "$SYSTEM_AS_ROOT" "$LEGACYSAR"
    printf 'KEEPVERITY=%s\nKEEPFORCEENCRYPT=%s\nPATCHVBMETAFLAG=%s\n' "$KEEPVERITY" "$KEEPFORCEENCRYPT" "$PATCHVBMETAFLAG"
    printf 'RECOVERYMODE=%s\nVENDORBOOT=%s\nSLOT=%s\n' "$RECOVERYMODE" "$VENDORBOOT" "$SLOT"
    printf 'INPUT_SHA256=%s\n' "$patch_input_sha"
} > "$patch_output_dir/environment.txt"
cat "$patch_output_dir/environment.txt"

# Use only the official image patcher. SOURCEDMODE preserves our non-root
# environment and abort override. Its only target is the local copied image.
export KEEPVERITY KEEPFORCEENCRYPT PATCHVBMETAFLAG RECOVERYMODE LEGACYSAR
SOURCEDMODE=true
. ./boot_patch.sh ./input-recovery.img > "$patch_output_dir/patch.log" 2>&1
patch_status=$?
cat "$patch_output_dir/patch.log"
[ "$patch_status" = 0 ] || patch_die "Image patch failed; retain patch.log"
[ -f new-boot.img ] && [ ! -L new-boot.img ] || patch_die "No regular patched image produced"
patch_size=$(stat -c %s new-boot.img)
[ "$patch_size" -gt 0 ] && [ "$patch_size" -le 33554432 ] || patch_die "Patched image exceeds the 32 MiB recovery partition"
[ "$(patch_hash input-recovery.img)" = "$patch_input_sha" ] || patch_die "Working input unexpectedly changed"
[ "$(patch_hash "$patch_input")" = "$patch_input_sha" ] || patch_die "Original input unexpectedly changed"

# Unpack the candidate separately, verify embedded config and recovery DTBO.
(
    cd "$patch_output_dir/verify" || exit 1
    "$patch_work_dir/magiskboot" unpack "$patch_work_dir/new-boot.img" || exit 1
    "$patch_work_dir/magiskboot" cpio ramdisk.cpio test
    [ "$?" = 1 ] || exit 1
    "$patch_work_dir/magiskboot" cpio ramdisk.cpio 'extract .backup/.magisk ../patched-config.txt' || exit 1
    # The embedded configuration intentionally has mode 000; this extracted
    # diagnostic copy must be readable by the unprivileged verifier.
    chmod 600 ../patched-config.txt || exit 1
    grep -qx 'RECOVERYMODE=true' ../patched-config.txt || exit 1
    grep -qx 'KEEPVERITY=true' ../patched-config.txt || exit 1
    grep -qx 'KEEPFORCEENCRYPT=true' ../patched-config.txt || exit 1
    grep -qx 'VENDORBOOT=false' ../patched-config.txt || exit 1
    [ "$(patch_hash recovery_dtbo)" = 146a9aa3561bdb21d6574950d97ca37b64b2c1f3109f07bdb64379378fe04d49 ] || exit 1
) > "$patch_output_dir/verify.log" 2>&1 || patch_die "Candidate verification failed; retain verify.log"
cat "$patch_output_dir/verify.log"
mv new-boot.img "$patch_output_dir/$patch_output_name" || patch_die "Cannot save verified candidate"
sha256sum "$patch_output_dir/$patch_output_name" > "$patch_output_dir/output.sha256"
printf 'Prepared file: %s\nBytes: %s\n' "$patch_output_dir/$patch_output_name" "$patch_size"
cat "$patch_output_dir/output.sha256"
printf '%s\n' 'File preparation complete. No image was installed; bootability remains untested.'
if [ "$patch_profile" = twrp-bringup1 ]; then
    printf '%s\n' 'EXPERIMENTAL combined TWRP+Magisk image: validate standalone TWRP first, then test rooted Android and recovery boot paths separately.'
fi
