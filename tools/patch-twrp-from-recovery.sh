#!/sbin/sh
# File-only Magisk 31.1 patch preparation in this phone's TWRP environment.
# Invoke with the verified APK BusyBox ash, ASH_STANDALONE=1.
# Arguments: asset directory, regular input image, expected SHA256, NEW /tmp directory.
# This script never flashes, erases, mounts or reboots anything.
die() { echo "ERROR: $*" >&2; exit 1; }
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$#" = 4 ] || die 'Expected assets, image, SHA256 and new output directory'
set -o standalone || die 'Use the APK BusyBox ash'
[ "$(id -u)" = 0 ] || die 'Requires the recovery shell'
[ "$(getprop ro.product.device)" = OP486C ] || die 'Wrong device'
[ "$(getprop ro.product.model)" = CPH1923 ] || die 'Wrong model'
[ "$(getprop ro.twrp.version)" = 3.7.0_9-OP486C-bringup1 ] || die 'Unexpected recovery'
[ "$(getprop ro.hardware)" = mt6765 ] || die 'Wrong hardware'
[ -z "$(getprop ro.boot.slot_suffix)" ] || die 'Unexpected slot'
grep -qx 'PARTNAME=vbmeta' /sys/class/block/mmcblk0p10/uevent || die 'Missing separate vbmeta'
[ "$(cat /sys/class/block/mmcblk0p10/size)" = 16384 ] || die 'Wrong vbmeta geometry'
grep -qx 'PARTNAME=userdata' /sys/class/block/mmcblk0p40/uevent || die 'Unexpected preinit partition'
assets=$(readlink -f "$1") || die 'Assets path'
input=$(readlink -f "$2") || die 'Input path'
expected=$3
output=$4
case "$assets" in /tmp/*) ;; *) die 'Assets must be under /tmp' ;; esac
case "$input" in /tmp/*) ;; *) die 'Input must be under /tmp' ;; esac
case "$output" in /tmp/op486c-patch-*) ;; *) die 'Output must be a new /tmp/op486c-patch-* directory' ;; esac
[ -f "$input" ] && [ ! -b "$input" ] && [ ! -c "$input" ] || die 'Input must be a regular file'
[ "$(stat -c %s "$input")" = 33554432 ] || die 'Input must be exactly 32 MiB'
[ "$(hash "$input")" = "$expected" ] || die 'Input hash mismatch'
[ ! -e "$output" ] && [ ! -L "$output" ] || die 'Output already exists'
(
  cd "$assets" || exit 1
  sha256sum -c <<'HASHES'
417866965cb3845c7ea085f1499393efcf65e6c7cf1321e7911a3bd7c25a6c8d  util_functions.sh
721e879b9ebdda200796d95dbe6f8e9776cfff89b7550fdb5ca77ac87dcede17  boot_patch.sh
4d60ab3f5a59ebb2ca863f2f514e6924401b581e9b64f602665c008177626651  busybox
fb0ba1b1f3472d34b8ae21edd3a69c2a44f46a3a7c34e85e37c6b2b57d22b9ec  magisk
c0c7cc1c8e1afb92bff602164f6aa1bb4103f5028d076216d8bef48496e2f4dc  magiskinit
97e9ec75731103d31c9e1effca7a50c6444309ce8f78c2ec27e9fe721da4bb54  magiskboot
edc355f90c76bed3ae4b93fd098cd15f5e688840ea5aa104d65ac9dd210ae1d7  init-ld
HASHES
) || die 'APK asset hashes differ'
umask 077
mkdir -m 700 "$output" || die 'Cannot create output'
for file in util_functions.sh boot_patch.sh busybox magisk magiskinit magiskboot init-ld; do
  cp "$assets/$file" "$output/$file" || die 'Asset copy failed'
done
cp "$input" "$output/input.img" || die 'Input copy failed'
cd "$output" || die 'Output path'
chmod 755 busybox magisk magiskinit magiskboot init-ld
# These flags derive from the verified physical layout and earlier stock-Android
# patch test, not TWRP's generic build properties. Preserve verity/encryption.
export BOOTMODE=false KEEPVERITY=true KEEPFORCEENCRYPT=true
export PATCHVBMETAFLAG=false RECOVERYMODE=true LEGACYSAR=true
export PREINITDEVICE=userdata
. ./util_functions.sh
# Avoid all installer cleanup/UI-pipe behavior; only the official file patcher runs.
ui_print() { echo "$*"; }
abort() { die "$*"; }
[ "$MAGISK_VER_CODE" = 31100 ] || die 'Wrong patcher version'
SOURCEDMODE=true
. ./boot_patch.sh ./input.img > patch.log 2>&1
result=$?
cat patch.log
[ "$result" = 0 ] || die 'Patcher failed'
[ "$(hash "$input")" = "$expected" ] || die 'Original changed'
[ "$(stat -c %s new-boot.img)" = 33554432 ] || die 'Unexpected output size'
mkdir verify
(
  cd verify || exit 1
  ../magiskboot unpack ../new-boot.img || exit 1
  ../magiskboot cpio ramdisk.cpio test
  [ "$?" = 1 ] || exit 1
  ../magiskboot cpio ramdisk.cpio 'extract .backup/.magisk ../patched-config.txt' || exit 1
  chmod 600 ../patched-config.txt
  grep -qx 'RECOVERYMODE=true' ../patched-config.txt || exit 1
  grep -qx 'KEEPVERITY=true' ../patched-config.txt || exit 1
  grep -qx 'KEEPFORCEENCRYPT=true' ../patched-config.txt || exit 1
  grep -qx 'PREINITDEVICE=userdata' ../patched-config.txt || exit 1
  [ "$(hash recovery_dtbo)" = 146a9aa3561bdb21d6574950d97ca37b64b2c1f3109f07bdb64379378fe04d49 ] || exit 1
) > verify.log 2>&1 || die 'Output verification failed'
sha256sum new-boot.img
echo 'File preparation complete; no firmware was installed.'
