#!/system/bin/sh
# PHH publishes these after reading the stock-compatible boot header.
# Reload the HAL once they exist, then reconnect keystore. Never reset keys.
i=0
while [ "$i" -lt 90 ]; do
    if [ -n "$(getprop ro.keymaster.xxx.release)" ] &&
       [ -n "$(getprop ro.keymaster.xxx.security_patch)" ] &&
       [ "$(getprop init.svc.vendor.keymaster-3-0)" = running ]; then
        setprop ctl.restart vendor.keymaster-3-0
        if [ "$(getprop init.svc.keystore)" = running ]; then
            setprop ctl.restart keystore
        fi
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done
exit 1
