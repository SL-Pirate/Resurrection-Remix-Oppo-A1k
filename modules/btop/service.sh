#!/system/bin/sh
BTOP_MODULE=${0%/*}
if [ -d /sbin ] && [ ! -e /sbin/btop ] && [ ! -L /sbin/btop ]; then
    ln -s "$BTOP_MODULE/run-btop" /sbin/btop
fi
