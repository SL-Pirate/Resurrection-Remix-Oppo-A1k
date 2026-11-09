#!/system/bin/sh
# Match the stock tee.rc directory setup even when crypto.state=unsupported.
# Never remove, replace, or clear existing security state.
DIR=/data/vendor/mcRegistry
if [ ! -e "$DIR" ] && [ ! -L "$DIR" ]; then
    mkdir -m 0775 "$DIR" || exit 1
    chown system:system "$DIR" || exit 1
    restorecon "$DIR" || exit 1
fi
