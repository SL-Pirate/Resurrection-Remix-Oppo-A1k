#!/system/bin/sh
# Experimental early-init RAM overlay for the verified OP486C vendor fstab.
# Called only by the associated Magisk overlay rc, using the pinned BusyBox.
# Does not format, decrypt, remount vendor rw, change properties, or write /data.
set -u
BB=${1:?pinned busybox path required}
TARGET=/vendor/etc/fstab.mt6765
RAMDIR=/dev/op486c-nofbe
RAMFILE=$RAMDIR/fstab.mt6765
STOCK_SHA=2049b44de9b4a5054198a70051ec31201f718203870a2d7a52e1fd967193ca10
PATCHED_SHA=1eee595a427b920d6fee95392664b3b79ffd492c67122fa4279897780d15d552
BUSYBOX_SHA=4d60ab3f5a59ebb2ca863f2f514e6924401b581e9b64f602665c008177626651

note() { printf '<6>OP486C_NOFBE: %s\n' "$*" > /dev/kmsg; }
fail() { note "REFUSED: $*"; exit 1; }
hash_file() {
    value=$("$BB" sha256sum "$1") || return 1
    printf '%s\n' "${value%% *}"
}

[ "${BB##*/}" = busybox ] || fail 'incorrect multicall basename'
[ "$(hash_file "$BB")" = "$BUSYBOX_SHA" ] || fail 'BusyBox hash mismatch'
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || fail 'fstab missing or symlink'
[ "$(hash_file "$TARGET")" = "$STOCK_SHA" ] || fail 'stock fstab hash mismatch'
# Verify both mountpoint and backing device in addition to the whole-file hash.
"$BB" awk '
    $1 == "/dev/block/platform/bootdevice/by-name/userdata" && $2 == "/data" &&
    $3 == "ext4" && $5 ~ /(^|,)fileencryption=aes-256-xts(,|$)/ { n++ }
    END { exit n != 1 }
' "$TARGET" || fail 'unexpected userdata row'

umask 077
# /dev is tmpfs. Do not reuse a directory left by any other action.
"$BB" mkdir -m 0700 "$RAMDIR" || fail 'RAM directory already exists or unavailable'
"$BB" sed '/^\/dev\/block\/platform\/bootdevice\/by-name\/userdata[[:space:]]/s/,fileencryption=aes-256-xts//' \
    "$TARGET" > "$RAMFILE" || fail 'RAM fstab generation failed'
[ "$(hash_file "$RAMFILE")" = "$PATCHED_SHA" ] || fail 'RAM fstab hash mismatch'
"$BB" chown 0:0 "$RAMFILE" || fail 'ownership setup failed'
"$BB" chmod 0644 "$RAMFILE" || fail 'mode setup failed'
# Preserve the verified target label (vendor_configs_file on this vendor build).
# The label belongs to the source inode and follows the bind mount.
"$BB" chcon --reference="$TARGET" "$RAMFILE" || fail 'SELinux label copy failed'
"$BB" mount -o bind "$RAMFILE" "$TARGET" || fail 'RAM bind mount failed'
[ "$(hash_file "$TARGET")" = "$PATCHED_SHA" ] || fail 'bound fstab verification failed'
note "APPLIED: userdata fileencryption token removed in RAM; sha256=$PATCHED_SHA"
exit 0
