#!/system/bin/sh
# Leave existing swap configuration alone; never reset an initialized device.
MODDIR=${0%/*}
exec >> "$MODDIR/service.log" 2>&1
date
BB=/data/adb/magisk/busybox
Z=/sys/block/zram0
DEV=/dev/block/zram0
n=0
while [ ! -b "$DEV" ] && [ "$n" -lt 30 ]; do
    sleep 2
    n=$((n + 1))
done
[ -b "$DEV" ] || exit 1
if grep -q zram0 /proc/swaps; then
    echo 'zRAM already active; unchanged.'
else
[ "$(cat "$Z/initstate")" = 0 ] || { echo 'zRAM already initialized; unchanged.'; exit 1; }
echo lz4 > "$Z/comp_algorithm" || exit 1
echo 1073741824 > "$Z/disksize" || exit 1
"$BB" mkswap "$DEV" || exit 1
/system/bin/swapon -p 100 "$DEV" || exit 1
fi
SWAPFILE=/data/adb/op486c-storage.swap
if [ -f "$SWAPFILE" ] && ! grep -q "$SWAPFILE" /proc/swaps; then
    /system/bin/swapon -p 10 "$SWAPFILE" || exit 1
fi
cat /proc/swaps
